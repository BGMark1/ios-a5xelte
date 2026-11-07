/* Root autorun for a reversible MobileGestalt cache experiment. */
#ifdef __APPLE__
typedef struct file FILE;
typedef struct directory DIR;
struct dirent {
    unsigned long long inode, seek;
    unsigned short reclen, namlen;
    unsigned char type;
    char d_name[1024];
};
extern FILE *fopen(const char *, const char *);
extern char *fgets(char *, int, FILE *);
extern unsigned long fread(void *, unsigned long, unsigned long, FILE *);
extern int ferror(FILE *);
extern int fclose(FILE *);
extern DIR *opendir(const char *);
extern struct dirent *readdir(DIR *);
extern int closedir(DIR *);
extern int access(const char *, int);
extern int chmod(const char *, unsigned short);
extern int rename(const char *, const char *);
extern int snprintf(char *, unsigned long, const char *, ...);
extern int strcmp(const char *, const char *);
extern void sync(void);
extern int *__error(void);
#define errno (*__error())
#define ENOENT 2
extern void herodrm_log(const char *, ...);
#else
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#define herodrm_log(...) do { printf(__VA_ARGS__); putchar('\n'); } while (0)
#endif

#ifndef DROP
#define DROP "/private/var/herolte"
#endif
#ifndef GROUPS
#define GROUPS "/private/var/containers/Shared/SystemGroup"
#endif
#define GROUP_NAME "systemgroup.com.apple.mobilegestaltcache"
#define CACHE_NAME "com.apple.MobileGestalt.plist"
#define BACKUP_SUFFIX ".herolte-screen-test"

enum { path_size = 1024 };
struct fingerprint {
    unsigned long long hash;
    unsigned long bytes;
};

static int fingerprint(const char *path, struct fingerprint *out)
{
    unsigned char buf[4096];
    FILE *file = fopen(path, "rb");
    if (!file)
        return 0;
    struct fingerprint result = {14695981039346656037ULL, 0};
    unsigned long n;
    while ((n = fread(buf, 1, sizeof(buf), file)) != 0) {
        result.bytes += n;
        if (result.bytes > 8UL * 1024 * 1024)
            break;
        for (unsigned long i = 0; i < n; ++i)
            result.hash = (result.hash ^ buf[i]) * 1099511628211ULL;
    }
    int ok = !ferror(file) && result.bytes != 0 && result.bytes <= 8UL * 1024 * 1024;
    fclose(file);
    if (ok)
        *out = result;
    return ok;
}

static int format_paths(const char *group, char *live, char *backup)
{
    int n = snprintf(live, path_size, "%s/%s/Library/Caches/%s", GROUPS, group, CACHE_NAME);
    if (n < 0 || n >= path_size)
        return 0;
    n = snprintf(backup, path_size, "%s%s", live, BACKUP_SUFFIX);
    return n >= 0 && n < path_size;
}

static int is_uuid(const char *name)
{
    for (unsigned i = 0; i < 36; ++i) {
        char c = name[i];
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            if (c != '-')
                return 0;
        } else if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F') ||
                     (c >= 'a' && c <= 'f'))) {
            return 0;
        }
    }
    return name[36] == '\0';
}

static int locate(char *live, char *backup, int restore)
{
    if (format_paths(GROUP_NAME, live, backup) &&
        (access(backup, 0) == 0 || (!restore && access(live, 0) == 0)))
        return 1;
    DIR *groups = opendir(GROUPS);
    if (!groups)
        return 0;
    struct dirent *entry;
    char candidate[path_size], saved[path_size];
    unsigned matches = 0;
    while ((entry = readdir(groups))) {
        if (is_uuid(entry->d_name) && format_paths(entry->d_name, candidate, saved) &&
            (access(saved, 0) == 0 || (!restore && access(candidate, 0) == 0))) {
            format_paths(entry->d_name, live, backup);
            if (++matches > 1)
                break;
        }
    }
    closedir(groups);
    return matches == 1;
}

int main(void)
{
    char mode[16], live[path_size], backup[path_size];
    FILE *file = fopen(DROP "/mg-cache-mode", "r");
    if (!file)
        return 1;
    int read = fgets(mode, sizeof(mode), file) != 0;
    fclose(file);
    int restore = read && strcmp(mode, "restore\n") == 0;
    if (!restore && (!read || strcmp(mode, "save\n") != 0))
        return 1;
    if (chmod(DROP, 0711) != 0 || chmod(DROP "/lib", 0711) != 0 || !locate(live, backup, restore)) {
        herodrm_log("mg-cache: no unique cache path, no move");
        return 2;
    }
    if (!restore && access(backup, 0) == 0) {
        herodrm_log("mg-cache: backup already present, no move");
        return 0;
    }
    if (!restore && errno != ENOENT)
        return 2;

    const char *from = restore ? backup : live;
    const char *to = restore ? live : backup;
    struct fingerprint before, after;
    if (!fingerprint(from, &before) || rename(from, to) != 0) {
        herodrm_log("mg-cache: %s move failed, errno %d", restore ? "restore" : "save", errno);
        return 3;
    }
    sync();
    if (!fingerprint(to, &after) || before.bytes != after.bytes || before.hash != after.hash) {
        herodrm_log("mg-cache: %s readback mismatch", restore ? "restore" : "save");
        return 4;
    }
    herodrm_log("mg-cache: %s verified, %lu bytes", restore ? "restore" : "save", after.bytes);
    return 0;
}
