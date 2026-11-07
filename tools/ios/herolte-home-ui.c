typedef void *object;
typedef void *selector;
typedef void *method;
typedef struct { double width, height, pixel_scale, radius; } icon_info;

extern object objc_getClass(const char *name);
extern object object_getClass(object value);
extern selector sel_registerName(const char *name);
extern method class_getInstanceMethod(object cls, selector sel);
extern const char *method_getTypeEncoding(method value);
extern void objc_msgSend(void);
extern char *strstr(const char *text, const char *needle);
extern void *dlopen(const char *path, int mode);
extern char *dlerror(void);
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
    object app = get(objc_getClass("UIApplication"), "sharedApplication");
    object windows = get(app, "windows");
    if (find_method(windows, "count") && find_method(windows, "objectAtIndex:")) {
        unsigned long count = ((unsigned long (*)(object, selector))objc_msgSend)(windows, sel_registerName("count"));
        for (unsigned long i = 0; i < count; ++i) {
            object window = ((object (*)(object, selector, unsigned long))objc_msgSend)(
                windows, sel_registerName("objectAtIndex:"), i);
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
    object string_class = objc_getClass("NSString");
    if (find_method(provider, "layoutForIconLocation:") && find_method(string_class, "stringWithUTF8String:")) {
        object location = ((object (*)(object, selector, const char *))objc_msgSend)(
            string_class, sel_registerName("stringWithUTF8String:"), "SBIconLocationRoot");
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
}
