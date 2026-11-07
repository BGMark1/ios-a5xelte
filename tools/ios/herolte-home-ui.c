typedef void *object;
typedef void *selector;
typedef void *method;
typedef struct { double width, height, pixel_scale, radius; } icon_info;
typedef struct { double x, y, width, height; } screen_rect;

extern object objc_getClass(const char *name);
extern object object_getClass(object value);
extern const char *class_getName(object cls);
extern selector sel_registerName(const char *name);
extern method class_getInstanceMethod(object cls, selector sel);
extern const char *method_getTypeEncoding(method value);
extern void objc_msgSend(void);
extern char *strstr(const char *text, const char *needle);
extern int access(const char *path, int mode);
extern void *dlopen(const char *path, int mode);
extern void *dlsym(void *handle, const char *name);
extern char *dlerror(void);
extern void CFRelease(const void *value);
extern char _dispatch_main_q;
extern unsigned long long dispatch_time(unsigned long long base, long long delta);
extern void dispatch_after_f(unsigned long long when, void *queue, void *context, void (*fn)(void *));
extern void herodrm_log(const char *format, ...);

static method find_method(object target, const char *name)
{
    return target ? class_getInstanceMethod(object_getClass(target), sel_registerName(name)) : 0;
}

static object get(object target, const char *name)
{
    return find_method(target, name) ?
        ((object (*)(object, selector))objc_msgSend)(target, sel_registerName(name)) : 0;
}

static double read_double(object target, const char *name)
{
    method getter = find_method(target, name);
    if (!getter || method_getTypeEncoding(getter)[0] != 'd')
        return -1;
    return ((double (*)(object, selector))objc_msgSend)(target, sel_registerName(name));
}

static screen_rect read_rect(object target, const char *name)
{
    method getter = find_method(target, name);
    if (!getter || !strstr(method_getTypeEncoding(getter), "{CGRect={CGPoint=dd}{CGSize=dd}}"))
        return (screen_rect){0};
    return ((screen_rect (*)(object, selector))objc_msgSend)(target, sel_registerName(name));
}

static object string(const char *value)
{
    object cls = objc_getClass("NSString");
    if (!find_method(cls, "stringWithUTF8String:"))
        return 0;
    return ((object (*)(object, selector, const char *))objc_msgSend)(
        cls, sel_registerName("stringWithUTF8String:"), value);
}

static double trait(object traits, const char *name)
{
    object key = string(name);
    if (!key || !find_method(traits, "objectForKey:"))
        return -1;
    object value = ((object (*)(object, selector, object))objc_msgSend)(
        traits, sel_registerName("objectForKey:"), key);
    return read_double(value, "doubleValue");
}

static void trace_screen(void *unused)
{
    (void)unused;
    if (access("/private/var/herolte/screen.trace", 0) != 0)
        return;
    object screen = get(objc_getClass("UIScreen"), "mainScreen");
    screen_rect bounds = read_rect(screen, "bounds");
    screen_rect native = read_rect(screen, "nativeBounds");
    herodrm_log("home screen trace: bounds %.0fx%.0f scale %.2f native %.0fx%.0f scale %.2f",
                bounds.width, bounds.height, read_double(screen, "scale"),
                native.width, native.height, read_double(screen, "nativeScale"));

    void *gestalt = dlopen("/usr/lib/libMobileGestalt.dylib", 2);
    object (*copy_answer)(object, object) = gestalt ? dlsym(gestalt, "MGCopyAnswer") : 0;
    if (!copy_answer)
        return;
    object scale_key = string("MainScreenScale");
    object artwork_key = string("ArtworkTraits");
    object scale = scale_key ? copy_answer(scale_key, 0) : 0;
    object artwork = artwork_key ? copy_answer(artwork_key, 0) : 0;
    herodrm_log("home screen trace: MG MainScreenScale %.2f ArtworkScaleFactor %.2f ArtworkDeviceSubType %.0f",
                read_double(scale, "doubleValue"), trait(artwork, "ArtworkScaleFactor"),
                trait(artwork, "ArtworkDeviceSubType"));
    if (scale)
        CFRelease(scale);
    if (artwork)
        CFRelease(artwork);
}

static void trace_status_views(object view, const char *window, unsigned depth, unsigned *remaining)
{
    if (!view || !*remaining || depth > 18)
        return;
    const char *name = class_getName(object_getClass(view));
    if (!depth || strstr(name, "StatusBar")) {
        method getter = find_method(view, "visualProviderClass");
        object provider = getter && method_getTypeEncoding(getter)[0] == '#' ?
            get(view, "visualProviderClass") : 0;
        herodrm_log("home status trace: window %s depth %u view %s provider %s",
                    window, depth, name, provider ? class_getName(provider) : "-");
        --*remaining;
    }
    object children = get(view, "subviews");
    if (!find_method(children, "count") || !find_method(children, "objectAtIndex:"))
        return;
    unsigned long count = ((unsigned long (*)(object, selector))objc_msgSend)(children, sel_registerName("count"));
    for (unsigned long i = 0; i < count && *remaining; ++i) {
        object child = ((object (*)(object, selector, unsigned long))objc_msgSend)(
            children, sel_registerName("objectAtIndex:"), i);
        trace_status_views(child, window, depth + 1, remaining);
    }
}

static int hide_status_fallback(object view, object status_bar, unsigned depth)
{
    if (!view || depth > 30)
        return 0;
    object cls = object_getClass(view);
    if (cls == objc_getClass("_UIStatusBar") || cls == objc_getClass("UIStatusBar"))
        status_bar = view;
    object fallback = objc_getClass("_UIStatusBarVisualProvider_Fallback");
    int is_fallback = status_bar == view && fallback &&
        get(view, "visualProviderClass") == fallback;
    if (!is_fallback && status_bar && find_method(view, "isKindOfClass:") &&
        ((_Bool (*)(object, selector, object))objc_msgSend)(
            view, sel_registerName("isKindOfClass:"), objc_getClass("UILabel"))) {
        object label = get(view, "text");
        const char *text = find_method(label, "UTF8String") ?
            ((const char *(*)(object, selector))objc_msgSend)(label, sel_registerName("UTF8String")) : 0;
        is_fallback = text && strstr(text, "rdar:45025538") != 0;
    }
    if (is_fallback && find_method(status_bar, "setHidden:")) {
        ((void (*)(object, selector, _Bool))objc_msgSend)(status_bar, sel_registerName("setHidden:"), 1);
        return 1;
    }
    object children = get(view, "subviews");
    if (!find_method(children, "count") || !find_method(children, "objectAtIndex:"))
        return 0;
    unsigned long count = ((unsigned long (*)(object, selector))objc_msgSend)(children, sel_registerName("count"));
    int hidden = 0;
    for (unsigned long i = 0; i < count; ++i) {
        object child = ((object (*)(object, selector, unsigned long))objc_msgSend)(
            children, sel_registerName("objectAtIndex:"), i);
        hidden += hide_status_fallback(child, status_bar, depth + 1);
    }
    return hidden;
}

static void check_status_bars(void *unused)
{
    (void)unused;
    static unsigned checks;
    static int reported;
    static int trace;
    if (!checks)
        trace = access("/private/var/herolte/status.trace", 0) == 0;
    unsigned trace_remaining = trace && (checks == 25 || checks == 65) ? 40 : 0;
    object app = get(objc_getClass("UIApplication"), "sharedApplication");
    object windows = get(app, "windows");
    if (find_method(windows, "count") && find_method(windows, "objectAtIndex:")) {
        unsigned long count = ((unsigned long (*)(object, selector))objc_msgSend)(windows, sel_registerName("count"));
        for (unsigned long i = 0; i < count; ++i) {
            object window = ((object (*)(object, selector, unsigned long))objc_msgSend)(
                windows, sel_registerName("objectAtIndex:"), i);
            if (trace_remaining && window)
                trace_status_views(window, class_getName(object_getClass(window)), 0, &trace_remaining);
            if (hide_status_fallback(window, 0, 0) && !reported) {
                reported = 1;
                herodrm_log("home status: hid UIKit diagnostic status bar");
            }
        }
    }
    if (++checks < 90)
        dispatch_after_f(dispatch_time(0, 2000000000LL), &_dispatch_main_q, 0, check_status_bars);
    else if (!reported)
        herodrm_log("home status: no diagnostic status bar matched");
}

static void adjust_icons(void *unused)
{
    (void)unused;
    static unsigned attempts;
    object controller = get(objc_getClass("SBIconController"), "sharedInstance");
    object manager = get(controller, "iconManager");
    object provider = get(manager, "listLayoutProvider");
    object config = 0;
    if (find_method(provider, "layoutForIconLocation:")) {
        object location = string("SBIconLocationRoot");
        if (!location)
            return;
        object layout = ((object (*)(object, selector, object))objc_msgSend)(
            provider, sel_registerName("layoutForIconLocation:"), location);
        config = get(layout, "layoutConfiguration");
    }
    if (!config && ++attempts < 8) {
        dispatch_after_f(dispatch_time(0, 5000000000LL), &_dispatch_main_q, 0, adjust_icons);
        return;
    }

    method getter = find_method(config, "iconImageInfo");
    method setter = find_method(config, "setIconImageInfo:");
    if (!getter || !setter || !strstr(method_getTypeEncoding(getter), "{CGSize=dd}dd}") ||
        !strstr(method_getTypeEncoding(setter), "{CGSize=dd}dd}")) {
        herodrm_log("home icon size: unsupported layout or icon size ABI");
        return;
    }

    selector read_info = sel_registerName("iconImageInfo");
    icon_info info = ((icon_info (*)(object, selector))objc_msgSend)(config, read_info);
    if (!(info.width >= 40 && info.width <= 76 && info.height >= 40 && info.height <= 76 &&
          info.pixel_scale >= 1 && info.pixel_scale <= 3 && info.radius >= 0 && info.radius <= 24)) {
        herodrm_log("home icon size: unexpected icon dimensions");
        return;
    }
    double width = info.width;
    info.width *= 1.08;
    info.height *= 1.08;
    info.radius *= 1.08;
    ((void (*)(object, selector, icon_info))objc_msgSend)(config, sel_registerName("setIconImageInfo:"), info);
    if (find_method(manager, "layoutIconListsWithAnimationType:forceRelayout:")) {
        ((void (*)(object, selector, long, int))objc_msgSend)(
            manager, sel_registerName("layoutIconListsWithAnimationType:forceRelayout:"), 0, 1);
    }
    icon_info actual = ((icon_info (*)(object, selector))objc_msgSend)(config, read_info);
    herodrm_log("home icon size: width %.2f -> %.2f pt", width, actual.width);
}

__attribute__((constructor)) static void start(void)
{
    if (!dlopen("/private/var/herolte/lib/libherosb-base.dylib", 2)) {
        const char *error = dlerror();
        herodrm_log("home icon size: background library failed: %s", error ? error : "unknown");
        return;
    }
    dispatch_after_f(dispatch_time(0, 15000000000LL), &_dispatch_main_q, 0, adjust_icons);
    dispatch_after_f(dispatch_time(0, 10000000000LL), &_dispatch_main_q, 0, check_status_bars);
    dispatch_after_f(dispatch_time(0, 20000000000LL), &_dispatch_main_q, 0, trace_screen);
}
