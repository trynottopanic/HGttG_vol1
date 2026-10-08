/* RG35XX H presentation adapter. Semantic layout and input remain in Guide View. */
#define _POSIX_C_SOURCE 200809L
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <gbm.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define SLOTS 32
#define TEXTURE_BUDGET (16U * 1024U * 1024U)
struct frame { struct gbm_bo *bo; uint32_t id; int fd; };
struct texture { GLuint id; unsigned width, height, bytes; };
struct gpu {
    int fd, pending, acquired;
    uint32_t connector, crtc;
    drmModeModeInfo mode;
    drmModeCrtc *saved;
    struct gbm_device *device;
    struct gbm_surface *window;
    EGLDisplay display;
    EGLContext context;
    EGLSurface surface;
    struct frame *current, *next;
    struct texture textures[SLOTS];
    unsigned bytes;
    GLuint program, planet_program;
    GLint opacity;
};

static double monotonic(void) {
    struct timespec now; clock_gettime(CLOCK_MONOTONIC, &now);
    return now.tv_sec + now.tv_nsec / 1000000000.0;
}
static void flipped(int fd, unsigned sequence, unsigned sec, unsigned usec, void *data) {
    (void)fd; (void)sequence; (void)sec; (void)usec;
    ((struct gpu *)data)->pending = 0;
}
static int drain(struct gpu *g, int milliseconds) {
    double deadline = monotonic() + milliseconds / 1000.0;
    drmEventContext events = {.version=DRM_EVENT_CONTEXT_VERSION, .page_flip_handler=flipped};
    while (g->pending) {
        int remaining = (int)ceil((deadline-monotonic())*1000);
        if (remaining <= 0) return -1;
        struct pollfd p = {.fd=g->fd, .events=POLLIN};
        int result = poll(&p, 1, remaining);
        if (result < 0 && errno == EINTR) continue;
        if (result <= 0 || !(p.revents & POLLIN) || drmHandleEvent(g->fd, &events)) return -1;
    }
    return 0;
}
static uint32_t crtc_for(int fd, drmModeRes *res, drmModeConnector *con) {
    drmModeEncoder *encoder = drmModeGetEncoder(fd, con->encoder_id);
    uint32_t id = encoder ? encoder->crtc_id : 0;
    drmModeFreeEncoder(encoder);
    for (int i=0; !id && i<con->count_encoders; ++i) {
        encoder = drmModeGetEncoder(fd, con->encoders[i]);
        if (!encoder) continue;
        for (int j=0; j<res->count_crtcs; ++j)
            if (encoder->possible_crtcs & (1U<<j)) { id=res->crtcs[j]; break; }
        drmModeFreeEncoder(encoder);
    }
    return id;
}
static int display_open(struct gpu *g) {
    for (int i=0; i<16; ++i) {
        char path[64]; snprintf(path, sizeof(path), "/dev/dri/card%d", i);
        int fd = open(path, O_RDWR|O_CLOEXEC);
        if (fd < 0) continue;
        drmVersionPtr version=drmGetVersion(fd);
        bool board = version && version->name && strcmp(version->name,"sun4i-drm")==0;
        drmFreeVersion(version);
        if (!board) { close(fd); continue; }
        drmModeRes *res=drmModeGetResources(fd);
        if (!res) { close(fd); continue; }
        for (int j=0; j<res->count_connectors; ++j) {
            drmModeConnector *con=drmModeGetConnector(fd,res->connectors[j]);
            if (con && con->connection==DRM_MODE_CONNECTED &&
                (con->connector_type==DRM_MODE_CONNECTOR_DPI || con->connector_type==DRM_MODE_CONNECTOR_DSI)) {
                for (int k=0; k<con->count_modes; ++k) {
                    if (con->modes[k].hdisplay!=640 || con->modes[k].vdisplay!=480) continue;
                    uint32_t crtc=crtc_for(fd,res,con);
                    drmModeCrtc *saved=crtc ? drmModeGetCrtc(fd,crtc) : NULL;
                    if (!saved || !saved->mode_valid || !saved->buffer_id) { drmModeFreeCrtc(saved); continue; }
                    g->fd=fd; g->connector=con->connector_id; g->crtc=crtc;
                    g->mode=con->modes[k]; g->saved=saved;
                    drmModeFreeConnector(con); drmModeFreeResources(res);
                    return 0;
                }
            }
            drmModeFreeConnector(con);
        }
        drmModeFreeResources(res); close(fd);
    }
    return -1;
}
static GLuint shader(GLenum type, const char *source) {
    GLuint s=glCreateShader(type); GLint ok=0;
    glShaderSource(s,1,&source,NULL); glCompileShader(s); glGetShaderiv(s,GL_COMPILE_STATUS,&ok);
    if (!ok) { glDeleteShader(s); return 0; } return s;
}
static int egl_open(struct gpu *g) {
    g->device=gbm_create_device(g->fd);
    if (!g->device) return -1;
    g->window=gbm_surface_create(g->device,640,480,GBM_FORMAT_XRGB8888,GBM_BO_USE_SCANOUT|GBM_BO_USE_RENDERING);
    if (!g->window) return -1;
    PFNEGLGETPLATFORMDISPLAYEXTPROC platform=(PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
    g->display=platform ? platform(EGL_PLATFORM_GBM_KHR,g->device,NULL) : eglGetDisplay((EGLNativeDisplayType)g->device);
    if (g->display==EGL_NO_DISPLAY || !eglInitialize(g->display,NULL,NULL) || !eglBindAPI(EGL_OPENGL_ES_API)) return -1;
    const EGLint attributes[]={EGL_SURFACE_TYPE,EGL_WINDOW_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES2_BIT,
        EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,0,EGL_NONE};
    EGLConfig configs[128], config=NULL; EGLint count=0;
    if (!eglChooseConfig(g->display,attributes,configs,128,&count)) return -1;
    for (int i=0;i<count;++i) {
        EGLint visual=0;
        if (eglGetConfigAttrib(g->display,configs[i],EGL_NATIVE_VISUAL_ID,&visual) && (uint32_t)visual==GBM_FORMAT_XRGB8888) { config=configs[i]; break; }
    }
    if (!config) return -1;
    const EGLint context[]={EGL_CONTEXT_CLIENT_VERSION,2,EGL_NONE};
    g->context=eglCreateContext(g->display,config,EGL_NO_CONTEXT,context);
    if (g->context==EGL_NO_CONTEXT) return -1;
    g->surface=eglCreateWindowSurface(g->display,config,(EGLNativeWindowType)g->window,NULL);
    if (g->surface==EGL_NO_SURFACE || !eglMakeCurrent(g->display,g->surface,g->surface,g->context)) return -1;
    const char *renderer=(const char *)glGetString(GL_RENDERER);
    /* H700 has Mali-G31/Panfrost. Never label llvmpipe a GPU path. */
    if (!renderer || (!strstr(renderer,"Mali") && !strstr(renderer,"Panfrost"))) return -1;
    fprintf(stderr,"GUIDE_UI_RENDERER backend=gles2 renderer=%s texture_budget=%u\n",renderer,TEXTURE_BUDGET);
    GLuint vs=shader(GL_VERTEX_SHADER,"attribute vec2 pos;attribute vec2 uv;varying vec2 tex;void main(){tex=uv;gl_Position=vec4(pos,0.0,1.0);}");
    GLuint fs=shader(GL_FRAGMENT_SHADER,"precision mediump float;uniform sampler2D image;uniform float opacity;varying vec2 tex;void main(){vec4 c=texture2D(image,tex);gl_FragColor=vec4(c.rgb,c.a*opacity);}");
    if (!vs || !fs) { if(vs)glDeleteShader(vs);if(fs)glDeleteShader(fs);return -1; }
    g->program=glCreateProgram(); glAttachShader(g->program,vs); glAttachShader(g->program,fs);
    glBindAttribLocation(g->program,0,"pos");glBindAttribLocation(g->program,1,"uv");glLinkProgram(g->program);
    glDeleteShader(vs);glDeleteShader(fs);GLint ok=0;glGetProgramiv(g->program,GL_LINK_STATUS,&ok);
    if (!ok) return -1;
    g->opacity=glGetUniformLocation(g->program,"opacity");
    glUseProgram(g->program);glUniform1i(glGetUniformLocation(g->program,"image"),0);
    glEnable(GL_BLEND);glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);
    glViewport(0,0,640,480);eglSwapInterval(g->display,1);
    return glGetError()==GL_NO_ERROR ? 0 : -1;
}
static void free_frame(struct gbm_bo *bo, void *data) {
    (void)bo; struct frame *f=data;
    drmModeRmFB(f->fd,f->id); free(f);
}
static struct frame *frame_for(struct gpu *g, struct gbm_bo *bo) {
    struct frame *f=gbm_bo_get_user_data(bo);
    if (f) return f;
    f=calloc(1,sizeof(*f));if(!f)return NULL;f->bo=bo;f->fd=g->fd;
    if (drmModeAddFB(g->fd,640,480,24,32,gbm_bo_get_stride(bo),gbm_bo_get_handle(bo).u32,&f->id)) {free(f);return NULL;}
    gbm_bo_set_user_data(bo,f,free_frame);return f;
}
/* A failed release retains the whole context, including pending-event data.
 * The caller must retry release and cannot grant another display lease yet. */
int guide_gpu_close(struct gpu *g) {
    if (!g) return 0;
    if (g->pending && drain(g,1000)) return -1;
    if (g->acquired && drmModeSetCrtc(g->fd,g->saved->crtc_id,g->saved->buffer_id,
            g->saved->x,g->saved->y,&g->connector,1,&g->saved->mode)) return -1;
    if(g->next)gbm_surface_release_buffer(g->window,g->next->bo);
    if(g->current)gbm_surface_release_buffer(g->window,g->current->bo);
    if(g->context!=EGL_NO_CONTEXT) {
        for(int i=0;i<SLOTS;++i)if(g->textures[i].id)glDeleteTextures(1,&g->textures[i].id);
        if(g->program)glDeleteProgram(g->program);
        if(g->planet_program)glDeleteProgram(g->planet_program);
    }
    if(g->display!=EGL_NO_DISPLAY) {
        eglMakeCurrent(g->display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);
        if(g->surface!=EGL_NO_SURFACE)eglDestroySurface(g->display,g->surface);
        if(g->context!=EGL_NO_CONTEXT)eglDestroyContext(g->display,g->context);
        eglTerminate(g->display);
    }
    if(g->window)gbm_surface_destroy(g->window);
    if(g->device)gbm_device_destroy(g->device);
    drmModeFreeCrtc(g->saved);if(g->fd>=0)close(g->fd);free(g);return 0;
}
struct gpu *guide_gpu_open(void) {
    struct gpu *g=calloc(1,sizeof(*g));if(!g)return NULL;
    g->fd=-1;g->display=EGL_NO_DISPLAY;g->context=EGL_NO_CONTEXT;g->surface=EGL_NO_SURFACE;
    if(display_open(g) || egl_open(g)) {guide_gpu_close(g);return NULL;}return g;
}
int guide_gpu_upload(struct gpu *g, unsigned slot, unsigned width, unsigned height, const void *rgba, unsigned length) {
    if(!g || slot>=SLOTS || !width || !height || width>1024 || height>1024 || !rgba || length!=width*height*4)return -1;
    struct texture *t=&g->textures[slot];
    if(g->bytes-t->bytes+length>TEXTURE_BUDGET)return -1;
    if(!t->id)glGenTextures(1,&t->id);
    glBindTexture(GL_TEXTURE_2D,t->id);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
    glPixelStorei(GL_UNPACK_ALIGNMENT,1);
    if(t->width==width && t->height==height)glTexSubImage2D(GL_TEXTURE_2D,0,0,0,width,height,GL_RGBA,GL_UNSIGNED_BYTE,rgba);
    else glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,width,height,0,GL_RGBA,GL_UNSIGNED_BYTE,rgba);
    if(glGetError()!=GL_NO_ERROR)return -1;
    g->bytes=g->bytes-t->bytes+length;t->bytes=length;t->width=width;t->height=height;return 0;
}
int guide_gpu_update(struct gpu *g,unsigned slot,unsigned x,unsigned y,unsigned width,unsigned height,const void *rgba,unsigned length) {
    if(!g || slot>=SLOTS || !width || !height || width>1024 || height>1024 || !rgba || length!=width*height*4)return -1;
    struct texture *t=&g->textures[slot];
    if(!t->id || x>t->width || y>t->height || width>t->width-x || height>t->height-y)return -1;
    glBindTexture(GL_TEXTURE_2D,t->id);glPixelStorei(GL_UNPACK_ALIGNMENT,1);
    glTexSubImage2D(GL_TEXTURE_2D,0,x,y,width,height,GL_RGBA,GL_UNSIGNED_BYTE,rgba);
    return glGetError()==GL_NO_ERROR ? 0 : -1;
}
int guide_gpu_drop(struct gpu *g,unsigned slot) {
    if(!g || slot>=SLOTS)return -1;
    struct texture *t=&g->textures[slot];
    if(t->id)glDeleteTextures(1,&t->id);
    g->bytes-=t->bytes;memset(t,0,sizeof(*t));return 0;
}
int guide_gpu_begin(struct gpu *g) {
    if(!g || g->pending || g->next)return -1;
    glClearColor(0,0,0,1);glClear(GL_COLOR_BUFFER_BIT);glUseProgram(g->program);return 0;
}
int guide_gpu_draw(struct gpu *g,unsigned slot,float x,float y,float width,float height,float angle,float pivot_x,float pivot_y,float opacity) {
    if(!g || slot>=SLOTS || !g->textures[slot].id || !isfinite(x) || !isfinite(y) || !isfinite(width) || !isfinite(height) ||
       !isfinite(angle) || !isfinite(pivot_x) || !isfinite(pivot_y) || !isfinite(opacity) || width<=0 || height<=0 || opacity<0 || opacity>1)return -1;
    const float uv[]={0,0,1,0,0,1,1,1};float vertices[8];
    float radians=angle*0.017453292519943295f,c=cosf(radians),s=sinf(radians);
    for(int i=0;i<4;++i) {
        float px=x+(i&1)*width-pivot_x,py=y+(i>>1)*height-pivot_y;
        vertices[2*i]=(pivot_x+c*px-s*py)/320.0f-1.0f;
        vertices[2*i+1]=1.0f-(pivot_y+s*px+c*py)/240.0f;
    }
    glBindTexture(GL_TEXTURE_2D,g->textures[slot].id);glUniform1f(g->opacity,opacity);
    glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,vertices);glVertexAttribPointer(1,2,GL_FLOAT,GL_FALSE,0,uv);
    glEnableVertexAttribArray(0);glEnableVertexAttribArray(1);glDrawArrays(GL_TRIANGLE_STRIP,0,4);
    return glGetError()==GL_NO_ERROR ? 0 : -1;
}

/* Pixel-grid planet: exact integer texel base, bounded fractional coordinate.
 * The caller falls back near any texel boundary where float precision matters. */
int guide_gpu_planet(struct gpu *g,unsigned world,unsigned grid,unsigned fraction,unsigned shade_lut,
                     float x,float y,float width,float height,float turn,float phase) {
    if(!g || world>=SLOTS || grid>=SLOTS || fraction>=SLOTS || shade_lut>=SLOTS ||
       !g->textures[world].id || !g->textures[grid].id || !g->textures[fraction].id || !g->textures[shade_lut].id ||
       !isfinite(turn) || turn<0 || turn>=512 || !isfinite(phase) || phase<0 || phase>=1 || !isfinite(x) || !isfinite(y) ||
       width!=396 || height!=396)return -1;
    if(!g->planet_program) {
        GLint precision=0,range[2];glGetShaderPrecisionFormat(GL_FRAGMENT_SHADER,GL_HIGH_FLOAT,range,&precision);
        if(precision<23)return -1;
        GLuint vs=shader(GL_VERTEX_SHADER,"attribute vec2 pos;attribute vec2 uv;varying vec2 tex;void main(){tex=uv;gl_Position=vec4(pos,0.,1.);}");
        GLuint fs=shader(GL_FRAGMENT_SHADER,
          "precision highp float;uniform sampler2D image;uniform sampler2D grid;uniform sampler2D fraction;uniform sampler2D shade_lut;uniform float turn;uniform float phase;varying vec2 tex;"
          "void main(){vec4 a=floor(texture2D(grid,tex)*255.+.5);vec3 f=floor(texture2D(fraction,tex).rgb*255.+.5);"
          "float part=dot(f,vec3(65536.,256.,1.))/16777216.;float col=mod(a.r*256.+a.g+turn+floor(part+phase),512.);"
          "vec3 c=floor(texture2D(image,vec2((col+.5)/512.,(a.b+.5)/256.)).rgb*255.+.5);float row=(a.a+.5)/13.;"
          "vec3 shaded=vec3(texture2D(shade_lut,vec2((c.r+.5)/256.,row)).r,texture2D(shade_lut,vec2((c.g+.5)/256.,row)).r,texture2D(shade_lut,vec2((c.b+.5)/256.,row)).r);"
          "gl_FragColor=vec4(shaded,step(.5,a.a));}");
        if(!vs || !fs){if(vs)glDeleteShader(vs);if(fs)glDeleteShader(fs);return -1;}
        GLuint program=glCreateProgram();glAttachShader(program,vs);glAttachShader(program,fs);
        glBindAttribLocation(program,0,"pos");glBindAttribLocation(program,1,"uv");glLinkProgram(program);
        glDeleteShader(vs);glDeleteShader(fs);GLint ok=0;glGetProgramiv(program,GL_LINK_STATUS,&ok);
        if(!ok){glDeleteProgram(program);return -1;}g->planet_program=program;
    }
    glUseProgram(g->planet_program);
    unsigned slots[]={world,grid,fraction,shade_lut};const char *names[]={"image","grid","fraction","shade_lut"};
    for(int i=0;i<4;++i){glActiveTexture(GL_TEXTURE0+i);glBindTexture(GL_TEXTURE_2D,g->textures[slots[i]].id);glUniform1i(glGetUniformLocation(g->planet_program,names[i]),i);}
    glUniform1f(glGetUniformLocation(g->planet_program,"turn"),turn);
    glUniform1f(glGetUniformLocation(g->planet_program,"phase"),phase);
    const float uv[]={0,0,1,0,0,1,1,1};
    float v[]={x/320-1,1-y/240,(x+width)/320-1,1-y/240,x/320-1,1-(y+height)/240,(x+width)/320-1,1-(y+height)/240};
    glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,v);glVertexAttribPointer(1,2,GL_FLOAT,GL_FALSE,0,uv);
    glEnableVertexAttribArray(0);glEnableVertexAttribArray(1);glDrawArrays(GL_TRIANGLE_STRIP,0,4);
    glActiveTexture(GL_TEXTURE0);glUseProgram(g->program);
    return glGetError()==GL_NO_ERROR?0:-1;
}
/* Consecutive, already ordered sprites sharing one atlas. No global reordering. */
int guide_gpu_batch(struct gpu *g,unsigned slot,unsigned count,const float *quads,
                    int clip_x,int clip_y,int clip_w,int clip_h) {
    if(!g || slot>=SLOTS || !g->textures[slot].id || !quads || count<1 || count>512 ||
       clip_x<0 || clip_y<0 || clip_w<1 || clip_h<1 || clip_x+clip_w>640 || clip_y+clip_h>480)return -1;
    float vertices[512*6*4];const int corner[]={0,1,2,2,1,3};
    for(unsigned i=0;i<count;++i){const float *q=quads+8*i;
        for(int k=0;k<8;++k)if(!isfinite(q[k]))return -1;
        if(q[2]<=0 || q[3]<=0 || q[4]<0 || q[5]<0 || q[6]>1 || q[7]>1 || q[6]<=q[4] || q[7]<=q[5])return -1;
        for(int j=0;j<6;++j){int c=corner[j];float *v=vertices+24*i+4*j;
            v[0]=(q[0]+(c&1)*q[2])/320-1;v[1]=1-(q[1]+(c>>1)*q[3])/240;
            v[2]=(c&1)?q[6]:q[4];v[3]=(c>>1)?q[7]:q[5];}
    }
    glUseProgram(g->program);glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,g->textures[slot].id);glUniform1f(g->opacity,1);
    glEnable(GL_SCISSOR_TEST);glScissor(clip_x,480-clip_y-clip_h,clip_w,clip_h);
    glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,4*sizeof(float),vertices);
    glVertexAttribPointer(1,2,GL_FLOAT,GL_FALSE,4*sizeof(float),vertices+2);
    glEnableVertexAttribArray(0);glEnableVertexAttribArray(1);glDrawArrays(GL_TRIANGLES,0,6*count);glDisable(GL_SCISSOR_TEST);
    return glGetError()==GL_NO_ERROR?0:-1;
}
int guide_gpu_present(struct gpu *g) {
    if(!g || !eglSwapBuffers(g->display,g->surface))return -1;
    struct gbm_bo *bo=gbm_surface_lock_front_buffer(g->window);if(!bo)return -1;
    g->next=frame_for(g,bo);
    if(!g->next){gbm_surface_release_buffer(g->window,bo);return -1;}
    if(!g->acquired) {
        if(drmModeSetCrtc(g->fd,g->crtc,g->next->id,0,0,&g->connector,1,&g->mode))return -1;
        g->acquired=1;
    } else {
        if(drmModePageFlip(g->fd,g->crtc,g->next->id,DRM_MODE_PAGE_FLIP_EVENT,g))return -1;
        g->pending=1;if(drain(g,250))return -1;
    }
    if(g->current)gbm_surface_release_buffer(g->window,g->current->bo);
    g->current=g->next;g->next=NULL;return 0;
}
