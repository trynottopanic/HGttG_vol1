/* Exercise actual argument parsing and the page-flip wait with GPU calls replaced. */
#define main guide_animation_main
#include "guide-boot-animation.c"
#undef main
#include <assert.h>

static int test_mode, releases, polls;
static double test_time;
static struct drm_framebuffer test_frame = {.bo = (struct gbm_bo *)1, .id = 7};
static void *flip_data;
static int config_case;

EGLBoolean __wrap_eglChooseConfig(EGLDisplay display, const EGLint *attributes,
                                 EGLConfig *configs, EGLint size, EGLint *count)
{
    (void)display; (void)attributes;
    if (config_case == 3 || (config_case == 4 && configs != NULL)) return EGL_FALSE;
    *count = config_case == 2 ? 0 : 2;
    if (configs != NULL && *count == 2) {
        assert(size >= 2);
        configs[0] = (EGLConfig)(uintptr_t)1;
        configs[1] = (EGLConfig)(uintptr_t)2;
    }
    return EGL_TRUE;
}
EGLBoolean __wrap_eglGetConfigAttrib(EGLDisplay display, EGLConfig config,
                                    EGLint attribute, EGLint *value)
{
    (void)display;
    assert(attribute == EGL_NATIVE_VISUAL_ID);
    if (config_case == 5) return EGL_FALSE;
    *value = (config_case == 1 || config == (EGLConfig)(uintptr_t)1)
        ? GBM_FORMAT_ARGB8888 : GBM_FORMAT_XRGB8888;
    return EGL_TRUE;
}

EGLBoolean __wrap_eglSwapBuffers(EGLDisplay display, EGLSurface surface)
{ (void)display; (void)surface; return EGL_TRUE; }
struct gbm_bo *__wrap_gbm_surface_lock_front_buffer(struct gbm_surface *surface)
{ (void)surface; return test_frame.bo; }
void *__wrap_gbm_bo_get_user_data(struct gbm_bo *bo)
{ (void)bo; return &test_frame; }
void __wrap_gbm_surface_release_buffer(struct gbm_surface *surface, struct gbm_bo *bo)
{ (void)surface; (void)bo; releases++; }
int __wrap_drmModePageFlip(int fd, uint32_t crtc, uint32_t fb, uint32_t flags, void *data)
{ (void)fd; (void)crtc; (void)fb; (void)flags; flip_data = data; return 0; }
int __wrap_clock_gettime(clockid_t clock, struct timespec *value)
{ (void)clock; test_time += .1; value->tv_sec = (time_t)test_time;
  value->tv_nsec = (long)((test_time - value->tv_sec) * 1e9); return 0; }
int __wrap_select(int nfds, fd_set *readfds, fd_set *writefds, fd_set *exceptfds, struct timeval *timeout)
{
    (void)nfds; (void)readfds; (void)writefds; (void)exceptfds; (void)timeout;
    polls++;
    if (test_mode == 1) { stop_requested = 1; errno = EINTR; return -1; }
    return test_mode >= 2 ? 1 : 0;
}
int __wrap_drmHandleEvent(int fd, drmEventContextPtr event)
{
    if (test_mode == 2) { errno = EIO; return -1; }
    event->page_flip_handler(fd, 0, 0, 0, flip_data);
    return 0;
}

int main(void)
{
    const EGLint attributes[] = {EGL_NONE};
    for (config_case = 0; config_case < 6; ++config_case) {
        EGLConfig selected = NULL;
        bool found = choose_scanout_config(EGL_NO_DISPLAY, attributes, &selected);
        if (config_case == 0) {
            assert(found && selected == (EGLConfig)(uintptr_t)2);
        } else assert(!found && selected == NULL);
    }
    puts("BOOT_ANIMATION_NATIVE_VISUAL_SELECTION_TESTS_PASS");
    double parsed;
    assert(parse_positive_double("8", &parsed) && parsed == 8);
    const char *invalid[] = {"nan", "inf", "0", "-1", "61", "8x", ""};
    for (size_t i = 0; i < sizeof(invalid)/sizeof(invalid[0]); i++)
        assert(!parse_positive_double(invalid[i], &parsed));
    for (test_mode = 0; test_mode < 4; test_mode++) {
        struct display display = {0};
        display.fd = 3;
        releases = polls = stop_requested = 0;
        test_time = 0;
        bool result = present_frame(&display, false);
        assert(polls > 0 && polls < 15);
        if (test_mode == 3) { assert(result && releases == 0 && display.current_fb == &test_frame); }
        else { assert(!result && releases == 1 && display.current_fb == NULL); }
    }
    puts("BOOT_ANIMATION_WAIT_AND_ARGUMENT_TESTS_PASS");
    return 0;
}
