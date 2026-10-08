#define main production_main
#include "guide-boot-animation.c"
#undef main
#include <assert.h>

int main(void) {
    EGLDisplay display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    assert(eglInitialize(display, NULL, NULL));
    const EGLint attributes[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT, EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_NONE};
    EGLConfig config; EGLint count;
    assert(eglChooseConfig(display, attributes, &config, 1, &count) && count);
    const EGLint size[] = {EGL_WIDTH, 640, EGL_HEIGHT, 480, EGL_NONE};
    EGLSurface surface = eglCreatePbufferSurface(display, config, size);
    const EGLint version[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
    EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, version);
    assert(eglMakeCurrent(display, surface, surface, context));
    struct renderer renderer;
    assert(initialize_renderer(&renderer, 640, 480));
    assert(renderer.frame_count == 75 && renderer.fps_numerator == 10);
    assert(animation_frame_at(&renderer, 0.0) == 0);
    assert(animation_frame_at(&renderer, 5.5) == 55);
    assert(animation_frame_at(&renderer, 7.49) == 74);
    assert(draw_frame(&renderer, 640, 480, 0.0));
    unsigned char first[4], final[4];
    glReadPixels(320, 240, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, first);
    assert(draw_frame(&renderer, 640, 480, 7.49));
    glReadPixels(320, 240, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, final);
    assert(memcmp(first, final, 3) != 0);
    destroy_renderer(&renderer);
    puts("PREBAKED_ECLIPSE_RENDER_PASS");
    return 0;
}
