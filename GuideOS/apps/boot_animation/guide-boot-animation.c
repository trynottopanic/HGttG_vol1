#define _POSIX_C_SOURCE 200809L

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <errno.h>
#include <fcntl.h>
#include <gbm.h>
#include <limits.h>
#include <math.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <time.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

#define TERRAIN_WIDTH 1024
#define TERRAIN_HEIGHT 512
#define CLOUD_WIDTH 2048
#define CLOUD_HEIGHT 512
#define MASK_WIDTH 80
#define MASK_HEIGHT 80
#define CAPTION_WIDTH 180
#define CAPTION_HEIGHT 24
#define CLOUD_PERIOD_SECONDS 20.0
#define DEFAULT_DURATION_SECONDS 7.5
#define DEFAULT_MAX_RUNTIME_SECONDS 9.5
#define ANIMATION_HEADER_SIZE 32U
#define ANIMATION_WIDTH 640U
#define ANIMATION_HEIGHT 480U
#define ANIMATION_FRAME_BYTES (ANIMATION_WIDTH * ANIMATION_HEIGHT * 2U)
#ifndef ASSET_DIRECTORY
#define ASSET_DIRECTORY "/usr/share/guideos/boot-animation"
#endif

static volatile sig_atomic_t stop_requested;

struct drm_framebuffer {
    struct gbm_bo *bo;
    uint32_t id;
};

struct display {
    int fd;
    uint32_t connector_id;
    uint32_t crtc_id;
    drmModeModeInfo mode;
    drmModeCrtc *saved_crtc;
    struct gbm_device *gbm_device;
    struct gbm_surface *gbm_surface;
    EGLDisplay egl_display;
    EGLContext egl_context;
    EGLSurface egl_surface;
    struct drm_framebuffer *current_fb;
};

struct renderer {
    GLuint program;
    GLuint vertex_buffer;
    GLuint animation_texture;
    FILE *animation;
    unsigned char *frame;
    uint32_t frame_count;
    uint32_t fps_numerator;
    uint32_t fps_denominator;
    uint32_t loaded_frame;
    GLuint terrain_texture;
    GLuint cloud_texture;
    GLuint road_texture;
    GLuint light_texture;
    GLuint silhouette_texture;
    GLuint caption_texture;
    GLuint words_texture;
    GLint resolution_uniform;
    GLint rotation_uniform;
    GLint cloud_phase_uniform;
    GLint stars_uniform;
};

static const char *vertex_shader_source =
    "attribute vec2 position;\n"
    "varying vec2 texture_coordinate;\n"
    "void main(void) {\n"
    "  texture_coordinate = vec2((position.x + 1.0) * 0.5, (1.0 - position.y) * 0.5);\n"
    "  gl_Position = vec4(position, 0.0, 1.0);\n"
    "}\n";

static const char *playback_fragment_shader_source =
    "precision mediump float;\n"
    "varying vec2 texture_coordinate;\n"
    "uniform sampler2D animation_frame;\n"
    "void main(void) { gl_FragColor = texture2D(animation_frame, texture_coordinate); }\n";

static const char *fragment_shader_source __attribute__((unused)) =
    "precision mediump float;\n"
    "uniform vec2 resolution;\n"
    "uniform float rotation;\n"
    "uniform float cloud_phase;\n"
    "uniform vec4 stars[12];\n"
    "uniform sampler2D terrain_map;\n"
    "uniform sampler2D cloud_map;\n"
    "uniform sampler2D road_map;\n"
    "uniform sampler2D light_map;\n"
    "uniform sampler2D silhouette_map;\n"
    "uniform sampler2D caption_map;\n"
    "uniform sampler2D words_map;\n"
    "const float PI = 3.14159265358979323846;\n"
    "float mask_at(vec2 uv) {\n"
    "  if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) return 0.0;\n"
    "  return texture2D(silhouette_map, uv).r;\n"
    "}\n"
    "float star_light(void) {\n"
    "  float light = 0.0;\n"
    "  for (int i = 0; i < 12; i++) {\n"
    "    vec2 distance = abs(gl_FragCoord.xy - stars[i].xy);\n"
    "    if (max(distance.x, distance.y) < stars[i].w * 0.5) light = stars[i].z;\n"
    "  }\n"
    "  return light;\n"
    "}\n"
    "void main(void) {\n"
    "  vec2 center = resolution * 0.5;\n"
    "  vec2 words_uv = (gl_FragCoord.xy - vec2(center.x - 300.0, resolution.y - 54.0)) / vec2(600.0, 24.0);\n"
    "  if (words_uv.x >= 0.0 && words_uv.x <= 1.0 && words_uv.y >= 0.0 && words_uv.y <= 1.0) {\n"
    "    float words = texture2D(words_map, vec2(words_uv.x, 1.0 - words_uv.y)).r * 0.80;\n"
    "    if (words > 0.0) { gl_FragColor = vec4(vec3(0.737, 0.871, 0.922) * words, 1.0); return; }\n"
    "  }\n"
    "  vec2 caption_size = vec2(180.0, 24.0);\n"
    "  vec2 caption_origin = vec2(center.x - caption_size.x * 0.5, 30.0);\n"
    "  vec2 caption_uv = (gl_FragCoord.xy - caption_origin) / caption_size;\n"
    "  if (caption_uv.x >= 0.0 && caption_uv.x <= 1.0 &&\n"
    "      caption_uv.y >= 0.0 && caption_uv.y <= 1.0) {\n"
    "    float caption = texture2D(caption_map, vec2(caption_uv.x, 1.0 - caption_uv.y)).r * 0.80;\n"
    "    if (caption > 0.0) {\n"
    "      gl_FragColor = vec4(vec3(0.737, 0.871, 0.922) * caption, 1.0);\n"
    "      return;\n"
    "    }\n"
    "  }\n"
    "  float radius = min(resolution.y * (1.0 / 3.0), 160.0);\n"
    "  vec2 p = (gl_FragCoord.xy - center) / radius;\n"
    "  vec2 mask_uv = p * 0.5 + 0.5;\n"
    "  float silhouette = mask_at(mask_uv);\n"
    "  vec2 mask_texel = vec2(1.0 / 80.0);\n"
    "  float shell_near = max(mask_at(mask_uv + vec2(mask_texel.x, 0.0)),\n"
    "                         mask_at(mask_uv - vec2(mask_texel.x, 0.0)));\n"
    "  float cloud_shell = silhouette < 0.5 ? shell_near * 0.82 : 0.0;\n"
    "  if (silhouette < 0.5 && shell_near < 0.5) {\n"
    "    gl_FragColor = vec4(vec3(0.88, 0.94, 1.0) * star_light(), 1.0);\n"
    "    return;\n"

    "  }\n"
    "  float rr = dot(p, p);\n"
    "  if (rr > 0.9998) { p *= sqrt(0.9998 / rr); rr = 0.9998; }\n"
    "  float z = sqrt(max(0.0, 1.0 - rr));\n"
    "  float lon = atan(p.x, z) / (2.0 * PI) + 0.5;\n"
    "  float lat = 0.5 - asin(p.y) / PI;\n"
    "  vec2 terrain_uv = vec2(fract(lon + rotation), lat);\n"
    "  vec3 terrain = texture2D(terrain_map, terrain_uv).rgb;\n"
    "  float road = texture2D(road_map, terrain_uv).r;\n"
    "  float settled_light = texture2D(light_map, terrain_uv).r;\n"
    "  terrain *= 1.0 - road * 0.08;\n"
    "  float cloud_u = fract(lon * 0.5 - cloud_phase * 0.5);\n"
    "  float cloud = texture2D(cloud_map, vec2(cloud_u, lat)).r;\n"
    "  float day_position = clamp((p.x + 0.48) / 0.78, 0.0, 1.0);\n"
    "  float transition = day_position * day_position * (3.0 - 2.0 * day_position);\n"
    "  vec3 cloud_color = vec3(0.949, 0.976, 1.0) * (0.32 + 0.68 * transition);\n"
    "  if (silhouette < 0.5) {\n"
    "    float shell_alpha = cloud * cloud_shell;\n"
    "    gl_FragColor = vec4(cloud_color * shell_alpha, 1.0);\n"
    "    return;\n"
    "  }\n"
    "  float illumination = 0.22 + 0.78 * transition;\n"
    "  vec3 color = terrain * illumination;\n"
    "  float emission = max(settled_light, road * 0.30) * (1.0 - transition);\n"
    "  emission *= 1.0 - cloud * 0.78;\n"
    "  color += vec3(1.0, 0.81, 0.44) * emission;\n"
    "  color = mix(color, cloud_color, cloud * (0.72 + 0.20 * transition));\n"
    "  float neighbor = min(min(mask_at(mask_uv + vec2(mask_texel.x, 0.0)),\n"
    "                           mask_at(mask_uv - vec2(mask_texel.x, 0.0))),\n"
    "                       min(mask_at(mask_uv + vec2(0.0, mask_texel.y)),\n"
    "                           mask_at(mask_uv - vec2(0.0, mask_texel.y))));\n"
    "  float rim = 1.0 - step(0.5, neighbor);\n"
    "  vec3 rim_color = mix(vec3(0.035, 0.173, 0.322), vec3(0.078, 0.435, 0.671), transition);\n"
    "  color = mix(color, rim_color, rim);\n"
    "  gl_FragColor = vec4(color, 1.0);\n"
    "}\n";

static void handle_signal(int signal_number)
{
    (void)signal_number;
    stop_requested = 1;
}

static double monotonic_seconds(void)
{
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) {
        return 0.0;
    }
    return (double)value.tv_sec + (double)value.tv_nsec / 1000000000.0;
}

static void fail_message(const char *operation)
{
    fprintf(stderr, "guide-boot-animation error=%s errno=%d detail=%s\n",
            operation, errno, strerror(errno));
}

static void page_flip_handler(int fd, unsigned int frame, unsigned int sec,
                              unsigned int usec, void *data)
{
    int *waiting = data;
    (void)fd;
    (void)frame;
    (void)sec;
    (void)usec;
    *waiting = 0;
}

static uint32_t find_crtc(int fd, drmModeRes *resources, drmModeConnector *connector)
{
    drmModeEncoder *encoder = NULL;
    uint32_t crtc_id = 0;
    int i;

    if (connector->encoder_id != 0) {
        encoder = drmModeGetEncoder(fd, connector->encoder_id);
        if (encoder != NULL && encoder->crtc_id != 0) {
            crtc_id = encoder->crtc_id;
        }
        drmModeFreeEncoder(encoder);
        if (crtc_id != 0) {
            return crtc_id;
        }
    }

    for (i = 0; i < connector->count_encoders; ++i) {
        int j;
        encoder = drmModeGetEncoder(fd, connector->encoders[i]);
        if (encoder == NULL) {
            continue;
        }
        for (j = 0; j < resources->count_crtcs; ++j) {
            if ((encoder->possible_crtcs & (1U << j)) != 0U) {
                crtc_id = resources->crtcs[j];
                break;
            }
        }
        drmModeFreeEncoder(encoder);
        if (crtc_id != 0) {
            return crtc_id;
        }
    }
    return 0;
}

static bool open_display(struct display *display)
{
    drmModeRes *resources = NULL;
    drmModeConnector *connector = NULL;
    char device_path[64] = {0};
    int device_index;
    int connector_index;
    int mode_index;

    memset(display, 0, sizeof(*display));
    display->fd = -1;
    display->egl_display = EGL_NO_DISPLAY;
    display->egl_context = EGL_NO_CONTEXT;
    display->egl_surface = EGL_NO_SURFACE;

    for (device_index = 0; device_index < 16 && connector == NULL; ++device_index) {
        snprintf(device_path, sizeof(device_path), "/dev/dri/card%d", device_index);
        display->fd = open(device_path, O_RDWR | O_CLOEXEC);
        if (display->fd < 0) {
            continue;
        }
        resources = drmModeGetResources(display->fd);
        if (resources == NULL) {
            close(display->fd);
            display->fd = -1;
            continue;
        }
        for (connector_index = 0; connector_index < resources->count_connectors; ++connector_index) {
            connector = drmModeGetConnector(display->fd, resources->connectors[connector_index]);
            if (connector != NULL && connector->connection == DRM_MODE_CONNECTED && connector->count_modes > 0) {
                break;
            }
            drmModeFreeConnector(connector);
            connector = NULL;
        }
        if (connector == NULL) {
            drmModeFreeResources(resources);
            resources = NULL;
            close(display->fd);
            display->fd = -1;
        } else {
            break;
        }
    }
    if (connector == NULL) {
        fprintf(stderr, "guide-boot-animation error=no-connected-display\n");
        return false;
    }
    mode_index = 0;
    for (int i = 0; i < connector->count_modes; ++i) {
        if ((connector->modes[i].type & DRM_MODE_TYPE_PREFERRED) != 0) {
            mode_index = i;
            break;
        }
    }
    display->connector_id = connector->connector_id;
    display->mode = connector->modes[mode_index];
    display->crtc_id = find_crtc(display->fd, resources, connector);
    drmModeFreeConnector(connector);
    drmModeFreeResources(resources);
    if (display->crtc_id == 0) {
        fprintf(stderr, "guide-boot-animation error=no-compatible-crtc\n");
        return false;
    }
    display->saved_crtc = drmModeGetCrtc(display->fd, display->crtc_id);
    fprintf(stdout, "guide-boot-animation drm=%s display=%ux%u connector=%u crtc=%u\n",
            device_path,
            display->mode.hdisplay, display->mode.vdisplay,
            display->connector_id, display->crtc_id);
    return true;
}

static bool choose_scanout_config(EGLDisplay display, const EGLint *attributes,
                                  EGLConfig *selected)
{
    EGLint count = 0;
    if (!eglChooseConfig(display, attributes, NULL, 0, &count) || count <= 0) {
        fprintf(stderr, "guide-boot-animation error=egl-config-list code=0x%x\n", eglGetError());
        return false;
    }
    EGLConfig *configs = calloc((size_t)count, sizeof(*configs));
    if (configs == NULL) return false;
    EGLint returned = 0;
    bool found = false;
    if (eglChooseConfig(display, attributes, configs, count, &returned) && returned <= count) {
        for (EGLint i = 0; i < returned; ++i) {
            EGLint visual = 0;
            if (!eglGetConfigAttrib(display, configs[i], EGL_NATIVE_VISUAL_ID, &visual)) {
                fprintf(stderr, "guide-boot-animation error=egl-config-attribute code=0x%x\n", eglGetError());
                break;
            }
            if ((uint32_t)visual == GBM_FORMAT_XRGB8888) {
                *selected = configs[i];
                fprintf(stdout, "guide-boot-animation config-visual=0x%x scanout=XRGB8888\n", visual);
                found = true;
                break;
            }
        }
    }
    free(configs);
    if (!found) fprintf(stderr, "guide-boot-animation error=no-xrgb8888-config\n");
    return found;
}

static bool initialize_egl(struct display *display)
{
    PFNEGLGETPLATFORMDISPLAYEXTPROC get_platform_display;
    EGLConfig config;
    const EGLint config_attributes[] = {
        EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE, 8,
        EGL_ALPHA_SIZE, 0,
        EGL_NONE
    };
    const EGLint context_attributes[] = {EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};

    display->gbm_device = gbm_create_device(display->fd);
    if (display->gbm_device == NULL) {
        fprintf(stderr, "guide-boot-animation error=gbm-device\n");
        return false;
    }
    display->gbm_surface = gbm_surface_create(display->gbm_device,
        display->mode.hdisplay, display->mode.vdisplay, GBM_FORMAT_XRGB8888,
        GBM_BO_USE_SCANOUT | GBM_BO_USE_RENDERING);
    if (display->gbm_surface == NULL) {
        fprintf(stderr, "guide-boot-animation error=gbm-surface\n");
        return false;
    }

    get_platform_display = (PFNEGLGETPLATFORMDISPLAYEXTPROC)
        eglGetProcAddress("eglGetPlatformDisplayEXT");
    if (get_platform_display != NULL) {
        display->egl_display = get_platform_display(EGL_PLATFORM_GBM_KHR,
                                                     display->gbm_device, NULL);
    } else {
        display->egl_display = eglGetDisplay((EGLNativeDisplayType)display->gbm_device);
    }
    if (display->egl_display == EGL_NO_DISPLAY ||
        !eglInitialize(display->egl_display, NULL, NULL) ||
        !eglBindAPI(EGL_OPENGL_ES_API)) {
        fprintf(stderr, "guide-boot-animation error=egl-initialize code=0x%x\n", eglGetError());
        return false;
    }
    if (!choose_scanout_config(display->egl_display, config_attributes, &config)) return false;
    display->egl_context = eglCreateContext(display->egl_display, config,
                                             EGL_NO_CONTEXT, context_attributes);
    if (display->egl_context == EGL_NO_CONTEXT) {
        fprintf(stderr, "guide-boot-animation error=egl-create-context code=0x%x\n", eglGetError());
        return false;
    }
    display->egl_surface = eglCreateWindowSurface(display->egl_display, config,
        (EGLNativeWindowType)display->gbm_surface, NULL);
    if (display->egl_surface == EGL_NO_SURFACE) {
        fprintf(stderr, "guide-boot-animation error=egl-create-window-surface code=0x%x\n", eglGetError());
        return false;
    }
    if (!eglMakeCurrent(display->egl_display, display->egl_surface,
                        display->egl_surface, display->egl_context)) {
        fprintf(stderr, "guide-boot-animation error=egl-make-current code=0x%x\n", eglGetError());
        return false;
    }
    eglSwapInterval(display->egl_display, 1);
    return true;
}

static GLuint compile_shader(GLenum type, const char *source)
{
    GLuint shader = glCreateShader(type);
    GLint compiled = GL_FALSE;
    glShaderSource(shader, 1, &source, NULL);
    glCompileShader(shader);
    glGetShaderiv(shader, GL_COMPILE_STATUS, &compiled);
    if (compiled != GL_TRUE) {
        char log[1024];
        GLsizei length = 0;
        glGetShaderInfoLog(shader, sizeof(log), &length, log);
        fprintf(stderr, "guide-boot-animation error=shader-compile detail=%.*s\n", (int)length, log);
        glDeleteShader(shader);
        return 0;
    }
    return shader;
}

static void *__attribute__((unused)) read_exact_file(const char *path, size_t expected_size)
{
    FILE *stream = fopen(path, "rb");
    void *data;
    size_t actual;
    if (stream == NULL) {
        fail_message(path);
        return NULL;
    }
    data = malloc(expected_size);
    if (data == NULL) {
        fclose(stream);
        return NULL;
    }
    actual = fread(data, 1, expected_size, stream);
    if (actual != expected_size || fgetc(stream) != EOF) {
        fprintf(stderr, "guide-boot-animation error=asset-size path=%s got=%zu expected=%zu\n",
                path, actual, expected_size);
        free(data);
        fclose(stream);
        return NULL;
    }
    fclose(stream);
    return data;
}

static bool __attribute__((unused)) upload_texture(GLuint *texture, GLenum format, int width, int height,
                           const char *path, size_t size)
{
    void *data = path != NULL ? read_exact_file(path, size) : calloc(size, 1);
    if (data == NULL) {
        return false;
    }
    glGenTextures(1, texture);
    glBindTexture(GL_TEXTURE_2D, *texture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, format, width, height, 0, format,
                 format == GL_RGB ? GL_UNSIGNED_SHORT_5_6_5 : GL_UNSIGNED_BYTE, data);
    free(data);
    if (glGetError() != GL_NO_ERROR) {
        fprintf(stderr, "guide-boot-animation error=texture-upload path=%s\n", path);
        return false;
    }
    return true;
}

static bool initialize_renderer(struct renderer *renderer, unsigned width, unsigned height)
{
    const GLfloat vertices[] = {-1.0f, -1.0f, 1.0f, -1.0f, -1.0f, 1.0f, 1.0f, 1.0f};
    GLuint vertex_shader = compile_shader(GL_VERTEX_SHADER, vertex_shader_source);
    GLuint fragment_shader = compile_shader(GL_FRAGMENT_SHADER, playback_fragment_shader_source);
    GLint linked = GL_FALSE;
    GLint position;
    const char *asset_directory = getenv("GUIDE_BOOT_ASSET_DIRECTORY");
    if (asset_directory == NULL || asset_directory[0] == '\0') asset_directory = ASSET_DIRECTORY;
    char animation_path[256];
    unsigned char header[ANIMATION_HEADER_SIZE];
    uint32_t fields[6];
    long file_size;

    memset(renderer, 0, sizeof(*renderer));
    renderer->loaded_frame = UINT32_MAX;
    if (width == 0 || height == 0) return false;
    snprintf(animation_path, sizeof(animation_path), "%s/boot-eclipse-v1.rgb565a", asset_directory);
    renderer->animation = fopen(animation_path, "rb");
    if (renderer->animation == NULL) {
        fail_message(animation_path);
        return false;
    }
    if (fread(header, 1, sizeof(header), renderer->animation) != sizeof(header) ||
        memcmp(header, "GOSANIM1", 8) != 0) {
        fprintf(stderr, "guide-boot-animation error=animation-header path=%s\n", animation_path);
        return false;
    }
    for (unsigned field = 0; field < 6; ++field) {
        unsigned offset = 8 + field * 4;
        fields[field] = (uint32_t)header[offset] |
                        ((uint32_t)header[offset + 1] << 8) |
                        ((uint32_t)header[offset + 2] << 16) |
                        ((uint32_t)header[offset + 3] << 24);
    }
    if (fields[0] != ANIMATION_WIDTH || fields[1] != ANIMATION_HEIGHT ||
        fields[2] == 0 || fields[2] > 600 || fields[3] == 0 || fields[3] > 120 ||
        fields[4] == 0 || fields[5] != ANIMATION_FRAME_BYTES ||
        (uint64_t)fields[2] * fields[4] * 2 != (uint64_t)fields[3] * 15) {
        fprintf(stderr, "guide-boot-animation error=animation-format path=%s\n", animation_path);
        return false;
    }
    if (fseek(renderer->animation, 0, SEEK_END) != 0 ||
        (file_size = ftell(renderer->animation)) < 0 ||
        (uint64_t)file_size != ANIMATION_HEADER_SIZE + (uint64_t)fields[2] * fields[5] ||
        fseek(renderer->animation, ANIMATION_HEADER_SIZE, SEEK_SET) != 0) {
        fprintf(stderr, "guide-boot-animation error=animation-size path=%s\n", animation_path);
        return false;
    }
    renderer->frame_count = fields[2];
    renderer->fps_numerator = fields[3];
    renderer->fps_denominator = fields[4];
    renderer->frame = malloc(ANIMATION_FRAME_BYTES);
    if (renderer->frame == NULL ||
        fread(renderer->frame, 1, ANIMATION_FRAME_BYTES, renderer->animation) != ANIMATION_FRAME_BYTES) {
        fprintf(stderr, "guide-boot-animation error=animation-first-frame path=%s\n", animation_path);
        return false;
    }
    renderer->loaded_frame = 0;
    if (vertex_shader == 0 || fragment_shader == 0) {
        return false;
    }
    renderer->program = glCreateProgram();
    glAttachShader(renderer->program, vertex_shader);
    glAttachShader(renderer->program, fragment_shader);
    glBindAttribLocation(renderer->program, 0, "position");
    glLinkProgram(renderer->program);
    glDeleteShader(vertex_shader);
    glDeleteShader(fragment_shader);
    glGetProgramiv(renderer->program, GL_LINK_STATUS, &linked);
    if (linked != GL_TRUE) {
        fprintf(stderr, "guide-boot-animation error=shader-link\n");
        return false;
    }
    glUseProgram(renderer->program);

    glGenBuffers(1, &renderer->vertex_buffer);
    glBindBuffer(GL_ARRAY_BUFFER, renderer->vertex_buffer);
    glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices, GL_STATIC_DRAW);
    position = glGetAttribLocation(renderer->program, "position");
    glEnableVertexAttribArray((GLuint)position);
    glVertexAttribPointer((GLuint)position, 2, GL_FLOAT, GL_FALSE, 0, NULL);
    glActiveTexture(GL_TEXTURE0);
    glGenTextures(1, &renderer->animation_texture);
    glBindTexture(GL_TEXTURE_2D, renderer->animation_texture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, ANIMATION_WIDTH, ANIMATION_HEIGHT, 0,
                 GL_RGB, GL_UNSIGNED_SHORT_5_6_5, renderer->frame);
    glUniform1i(glGetUniformLocation(renderer->program, "animation_frame"), 0);

    return glGetError() == GL_NO_ERROR;
}

static void framebuffer_destroy_callback(struct gbm_bo *bo, void *data)
{
    struct drm_framebuffer *framebuffer = data;
    int fd = gbm_device_get_fd(gbm_bo_get_device(bo));
    if (framebuffer->id != 0) {
        drmModeRmFB(fd, framebuffer->id);
    }
    free(framebuffer);
}

static struct drm_framebuffer *framebuffer_for_bo(struct gbm_bo *bo)
{
    struct drm_framebuffer *framebuffer = gbm_bo_get_user_data(bo);
    uint32_t handle;
    uint32_t stride;
    int fd;
    if (framebuffer != NULL) {
        return framebuffer;
    }
    framebuffer = calloc(1, sizeof(*framebuffer));
    if (framebuffer == NULL) {
        return NULL;
    }
    framebuffer->bo = bo;
    handle = gbm_bo_get_handle(bo).u32;
    stride = gbm_bo_get_stride(bo);
    fd = gbm_device_get_fd(gbm_bo_get_device(bo));
    if (drmModeAddFB(fd, gbm_bo_get_width(bo), gbm_bo_get_height(bo),
                     24, 32, stride, handle, &framebuffer->id) != 0) {
        fail_message("drm-add-framebuffer");
        free(framebuffer);
        return NULL;
    }
    gbm_bo_set_user_data(bo, framebuffer, framebuffer_destroy_callback);
    return framebuffer;
}

static bool present_frame(struct display *display, bool first_frame)
{
    struct gbm_bo *bo;
    struct drm_framebuffer *next;
    if (!eglSwapBuffers(display->egl_display, display->egl_surface)) {
        fprintf(stderr, "guide-boot-animation error=egl-swap code=0x%x\n", eglGetError());
        return false;
    }
    bo = gbm_surface_lock_front_buffer(display->gbm_surface);
    if (bo == NULL) {
        fprintf(stderr, "guide-boot-animation error=lock-front-buffer\n");
        return false;
    }
    next = framebuffer_for_bo(bo);
    if (next == NULL) {
        gbm_surface_release_buffer(display->gbm_surface, bo);
        return false;
    }
    if (first_frame) {
        if (drmModeSetCrtc(display->fd, display->crtc_id, next->id, 0, 0,
                           &display->connector_id, 1, &display->mode) != 0) {
            fail_message("drm-set-crtc");
            gbm_surface_release_buffer(display->gbm_surface, bo);
            return false;
        }
    } else {
        int waiting = 1;
        drmEventContext event = {0};
        event.version = DRM_EVENT_CONTEXT_VERSION;
        event.page_flip_handler = page_flip_handler;
        if (drmModePageFlip(display->fd, display->crtc_id, next->id,
                            DRM_MODE_PAGE_FLIP_EVENT, &waiting) != 0) {
            fail_message("drm-page-flip");
            gbm_surface_release_buffer(display->gbm_surface, bo);
            return false;
        }
        double flip_deadline = monotonic_seconds() + 1.0;
        while (waiting && !stop_requested) {
            fd_set descriptors;
            struct timeval timeout = {0, 100000};
            if (monotonic_seconds() >= flip_deadline) {
                fprintf(stderr, "guide-boot-animation error=drm-page-flip-timeout\n");
                gbm_surface_release_buffer(display->gbm_surface, bo);
                return false;
            }
            FD_ZERO(&descriptors);
            FD_SET(display->fd, &descriptors);
            int ready = select(display->fd + 1, &descriptors, NULL, NULL, &timeout);
            if (ready < 0 && errno != EINTR) {
                fail_message("drm-page-flip-wait");
                gbm_surface_release_buffer(display->gbm_surface, bo);
                return false;
            }
            if (ready > 0) {
                if (drmHandleEvent(display->fd, &event) != 0) {
                    fail_message("drm-event");
                    gbm_surface_release_buffer(display->gbm_surface, bo);
                    return false;
                }
            }
        }
        if (waiting) {
            gbm_surface_release_buffer(display->gbm_surface, bo);
            return false;
        }
    }
    if (display->current_fb != NULL) {
        gbm_surface_release_buffer(display->gbm_surface, display->current_fb->bo);
    }
    display->current_fb = next;
    return true;
}

/* Fixed distant stars: no drift, shared resource, or asset preparation work. */
static void __attribute__((unused)) update_stars(struct renderer *renderer, unsigned width, unsigned height, double elapsed)
{
    static const GLfloat positions[12][3] = {
        {64,96,4}, {118,208,4}, {46,365,4}, {14,438,4},
        {626,450,4}, {424,412,4}, {552,392,4}, {603,280,4},
        {527,187,4}, {575,60,4}, {411,56,4}, {192,48,4}
    };
    GLfloat stars[12][4];
    for (unsigned i = 0; i < 12; ++i) {
        double period = 5.5 + (i % 5) * 0.8;
        double phase = elapsed / period + i * 0.381966;
        double pulse = pow(fmax(0.0, cos(phase * 6.283185307179586)), 8.0);
        stars[i][0] = positions[i][0] * width / 640.0f;
        stars[i][1] = positions[i][1] * height / 480.0f;
        stars[i][2] = (GLfloat)(0.22 + 0.26 * pulse);
        stars[i][3] = positions[i][2];
    }
    glUniform4fv(renderer->stars_uniform, 12, &stars[0][0]);
}

static uint32_t animation_frame_at(const struct renderer *renderer, double elapsed)
{
    double scaled = elapsed * renderer->fps_numerator / renderer->fps_denominator;
    uint32_t frame = scaled > 0.0 ? (uint32_t)scaled : 0;
    return frame < renderer->frame_count ? frame : renderer->frame_count - 1;
}

static bool load_animation_frame(struct renderer *renderer, uint32_t frame)
{
    if (frame == renderer->loaded_frame) return true;
    uint64_t offset = ANIMATION_HEADER_SIZE + (uint64_t)frame * ANIMATION_FRAME_BYTES;
    if (offset > LONG_MAX || fseek(renderer->animation, (long)offset, SEEK_SET) != 0 ||
        fread(renderer->frame, 1, ANIMATION_FRAME_BYTES, renderer->animation) != ANIMATION_FRAME_BYTES) {
        fprintf(stderr, "guide-boot-animation error=animation-frame index=%u\n", frame);
        return false;
    }
    glBindTexture(GL_TEXTURE_2D, renderer->animation_texture);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, ANIMATION_WIDTH, ANIMATION_HEIGHT,
                    GL_RGB, GL_UNSIGNED_SHORT_5_6_5, renderer->frame);
    if (glGetError() != GL_NO_ERROR) {
        fprintf(stderr, "guide-boot-animation error=animation-upload index=%u\n", frame);
        return false;
    }
    renderer->loaded_frame = frame;
    return true;
}

static bool draw_frame(struct renderer *renderer, unsigned width, unsigned height, double elapsed)
{
    if (!load_animation_frame(renderer, animation_frame_at(renderer, elapsed))) return false;
    glViewport(0, 0, (GLsizei)width, (GLsizei)height);
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glUseProgram(renderer->program);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    return glGetError() == GL_NO_ERROR;
}

static void destroy_renderer(struct renderer *renderer)
{
    if (renderer->animation_texture != 0) glDeleteTextures(1, &renderer->animation_texture);
    if (renderer->animation != NULL) fclose(renderer->animation);
    free(renderer->frame);
    if (renderer->terrain_texture != 0) glDeleteTextures(1, &renderer->terrain_texture);
    if (renderer->cloud_texture != 0) glDeleteTextures(1, &renderer->cloud_texture);
    if (renderer->road_texture != 0) glDeleteTextures(1, &renderer->road_texture);
    if (renderer->light_texture != 0) glDeleteTextures(1, &renderer->light_texture);
    if (renderer->silhouette_texture != 0) glDeleteTextures(1, &renderer->silhouette_texture);
    if (renderer->words_texture != 0) glDeleteTextures(1, &renderer->words_texture);
    if (renderer->caption_texture != 0) glDeleteTextures(1, &renderer->caption_texture);
    if (renderer->vertex_buffer != 0) glDeleteBuffers(1, &renderer->vertex_buffer);
    if (renderer->program != 0) glDeleteProgram(renderer->program);
}

static void restore_display(struct display *display)
{
    if (display->saved_crtc != NULL && display->fd >= 0) {
        uint32_t connector = display->connector_id;
        if (drmModeSetCrtc(display->fd, display->saved_crtc->crtc_id,
                           display->saved_crtc->buffer_id,
                           display->saved_crtc->x, display->saved_crtc->y,
                           &connector, 1, &display->saved_crtc->mode) != 0) {
            fail_message("restore-display");
        }
    }
    if (display->current_fb != NULL && display->gbm_surface != NULL) {
        gbm_surface_release_buffer(display->gbm_surface, display->current_fb->bo);
        display->current_fb = NULL;
    }
    if (display->egl_display != EGL_NO_DISPLAY) {
        eglMakeCurrent(display->egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (display->egl_surface != EGL_NO_SURFACE) eglDestroySurface(display->egl_display, display->egl_surface);
        if (display->egl_context != EGL_NO_CONTEXT) eglDestroyContext(display->egl_display, display->egl_context);
        eglTerminate(display->egl_display);
    }
    if (display->gbm_surface != NULL) gbm_surface_destroy(display->gbm_surface);
    if (display->gbm_device != NULL) gbm_device_destroy(display->gbm_device);
    drmModeFreeCrtc(display->saved_crtc);
    if (display->fd >= 0) close(display->fd);
}

static bool parse_positive_double(const char *text, double *value)
{
    char *end = NULL;
    errno = 0;
    double parsed = strtod(text, &end);
    if (errno != 0 || end == text || *end != '\0' || !isfinite(parsed) || parsed <= 0.0 || parsed > 60.0) {
        return false;
    }
    *value = parsed;
    return true;
}

int main(int argc, char **argv)
{
    struct display display;
    struct renderer renderer;
    double duration = DEFAULT_DURATION_SECONDS;
    double maximum_runtime = DEFAULT_MAX_RUNTIME_SECONDS;
    double started;
    bool first_frame = true;
    bool renderer_ready = false;
    int result = EXIT_FAILURE;
    unsigned frames = 0, late_frames = 0;
    double frame_total_ms = 0, frame_max_ms = 0;

    setvbuf(stdout, NULL, _IOLBF, 0);

    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--duration") == 0 && i + 1 < argc) {
            if (!parse_positive_double(argv[++i], &duration)) return 2;
        } else if (strcmp(argv[i], "--max-runtime") == 0 && i + 1 < argc) {
            if (!parse_positive_double(argv[++i], &maximum_runtime)) return 2;
        } else {
            fprintf(stderr, "usage: %s [--duration SECONDS] [--max-runtime SECONDS]\n", argv[0]);
            return 2;
        }
    }
    if (duration >= maximum_runtime) {
        fprintf(stderr, "guide-boot-animation error=duration-must-be-below-max-runtime\n");
        return 2;
    }

    signal(SIGTERM, handle_signal);
    signal(SIGINT, handle_signal);
    if (!open_display(&display) || !initialize_egl(&display)) {
        restore_display(&display);
        return EXIT_FAILURE;
    }
    if (!initialize_renderer(&renderer, display.mode.hdisplay, display.mode.vdisplay)) {
        restore_display(&display);
        return EXIT_FAILURE;
    }
    renderer_ready = true;
    started = monotonic_seconds();

    while (!stop_requested) {
        double elapsed = monotonic_seconds() - started;
        if (elapsed >= duration) {
            fprintf(stdout, "guide-boot-animation handoff=duration elapsed=%.3f\n", elapsed);
            result = EXIT_SUCCESS;
            break;
        }
        if (elapsed >= maximum_runtime) {
            fprintf(stderr, "guide-boot-animation handoff=safety-timeout elapsed=%.3f\n", elapsed);
            result = EXIT_FAILURE;
            break;
        }
        double frame_started = monotonic_seconds();
        if (!draw_frame(&renderer, display.mode.hdisplay, display.mode.vdisplay, elapsed)) {
            break;
        }
        if (!present_frame(&display, first_frame)) {
            break;
        }
        double frame_ms = (monotonic_seconds() - frame_started) * 1000.0;
        frames++;
        frame_total_ms += frame_ms;
        if (frame_ms > frame_max_ms) frame_max_ms = frame_ms;
        if (frame_ms > 33.334) late_frames++;
        if (first_frame) {
            /* Playback starts when a frame is on screen, not during setup. */
            started = monotonic_seconds();
            fprintf(stdout, "guide-boot-animation first-frame=presented\n");
            const char *ready_fd = getenv("GUIDE_BOOT_READY_FD");
            if (ready_fd != NULL) {
                char *end = NULL;
                long fd = strtol(ready_fd, &end, 10);
                if (end == ready_fd || *end != '\0' || fd < 3 || fd > 1048576) break;
                ssize_t sent;
                do { sent = write((int)fd, "R", 1); } while (sent < 0 && errno == EINTR);
                close((int)fd);
                if (sent != 1) break;
            }
        }
        first_frame = false;
    }
    if (stop_requested) {
        fprintf(stdout, "guide-boot-animation handoff=signal\n");
        result = EXIT_SUCCESS;
    }
    if (renderer_ready) destroy_renderer(&renderer);
    fprintf(stdout, "GUIDE_VIDEO_METRICS {\"frames\":%u,\"late_frames\":%u,\"frame_mean_ms\":%.3f,\"frame_max_ms\":%.3f}\n",
            frames, late_frames, frames ? frame_total_ms / frames : 0, frame_max_ms);
    restore_display(&display);
    return result;
}
