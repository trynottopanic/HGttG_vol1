/* Offscreen host validation of the production shader and batch entry points.
 * Never installed. Software Mesa here is test evidence, not Deck GPU evidence. */
#include "guide_gpu.c"

struct gpu *guide_test_open(void) {
    struct gpu *g=calloc(1,sizeof(*g));if(!g)return NULL;
    PFNEGLGETPLATFORMDISPLAYEXTPROC platform=(PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
    g->display=platform?platform(EGL_PLATFORM_SURFACELESS_MESA,EGL_DEFAULT_DISPLAY,NULL):EGL_NO_DISPLAY;
    if(g->display==EGL_NO_DISPLAY || !eglInitialize(g->display,NULL,NULL) || !eglBindAPI(EGL_OPENGL_ES_API))goto failed;
    const EGLint attrs[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES2_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};
    EGLConfig config;EGLint count;if(!eglChooseConfig(g->display,attrs,&config,1,&count)||count!=1)goto failed;
    const EGLint context[]={EGL_CONTEXT_CLIENT_VERSION,2,EGL_NONE},surface[]={EGL_WIDTH,640,EGL_HEIGHT,480,EGL_NONE};
    g->context=eglCreateContext(g->display,config,EGL_NO_CONTEXT,context);
    g->surface=eglCreatePbufferSurface(g->display,config,surface);
    if(!eglMakeCurrent(g->display,g->surface,g->surface,g->context))goto failed;
    GLuint vs=shader(GL_VERTEX_SHADER,"attribute vec2 pos;attribute vec2 uv;varying vec2 tex;void main(){tex=uv;gl_Position=vec4(pos,0.,1.);}");
    GLuint fs=shader(GL_FRAGMENT_SHADER,"precision mediump float;uniform sampler2D image;uniform float opacity;varying vec2 tex;void main(){vec4 c=texture2D(image,tex);gl_FragColor=vec4(c.rgb,c.a*opacity);}");
    g->program=glCreateProgram();glAttachShader(g->program,vs);glAttachShader(g->program,fs);
    glBindAttribLocation(g->program,0,"pos");glBindAttribLocation(g->program,1,"uv");glLinkProgram(g->program);
    glDeleteShader(vs);glDeleteShader(fs);g->opacity=glGetUniformLocation(g->program,"opacity");
    glUseProgram(g->program);glUniform1i(glGetUniformLocation(g->program,"image"),0);
    glEnable(GL_BLEND);glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);glViewport(0,0,640,480);
    return g;
failed:
    if(g->display!=EGL_NO_DISPLAY)eglTerminate(g->display);
    free(g);return NULL;
}
int guide_test_read(struct gpu *g,void *rgba) {
    if(!g||!rgba)return -1;
    glFinish();glReadPixels(0,0,640,480,GL_RGBA,GL_UNSIGNED_BYTE,rgba);
    return glGetError()==GL_NO_ERROR?0:-1;
}
void guide_test_close(struct gpu *g) {
    if(!g)return;
    for(int i=0;i<SLOTS;++i)guide_gpu_drop(g,i);
    glDeleteProgram(g->program);if(g->planet_program)glDeleteProgram(g->planet_program);
    eglMakeCurrent(g->display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);
    eglDestroySurface(g->display,g->surface);eglDestroyContext(g->display,g->context);eglTerminate(g->display);free(g);
}
