// SPDX-License-Identifier: AGPL-3.0-or-later

#define _GNU_SOURCE
#include <alsa/asoundlib.h>
#include <dirent.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/input.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "libretro.h"
#include "guide_supervisor_protocol.h"

#define MAX_INPUTS 16

struct system_config {
    const char *id;
    const char *core;
    const char *folder;
    const char *extensions;
    const char *bios_folder;
};

static const struct system_config systems[] = {
    {"gb", "/usr/lib/guideos/emulation/cores/gambatte_libretro.so", "GB", ".gb", "GB"},
    {"gbc", "/usr/lib/guideos/emulation/cores/gambatte_libretro.so", "GBC", ".gbc,.gb", "GBC"},
    {"gba", "/usr/lib/guideos/emulation/cores/mgba_libretro.so", "GBA", ".gba", "GBA"},
    {"genesis", "/usr/lib/guideos/emulation/cores/genesis_plus_gx_libretro.so", "GENESIS", ".md,.gen,.bin,.smd", "GENESIS"},
    {"snes", "/usr/lib/guideos/emulation/cores/snes9x2010_libretro.so", "SNES", ".sfc,.smc", "SNES"},
    {"nes", "/usr/lib/guideos/emulation/cores/fceumm_libretro.so", "NES", ".nes,.fds,.unf,.unif", "NES"},
    {"ps1", "/usr/lib/guideos/emulation/cores/pcsx_rearmed_libretro.so", "PS1", ".chd,.cue,.m3u,.pbp", "PS1"}
};

struct core_api {
    void (*set_environment)(retro_environment_t);
    void (*set_video_refresh)(retro_video_refresh_t);
    void (*set_audio_sample)(retro_audio_sample_t);
    void (*set_audio_sample_batch)(retro_audio_sample_batch_t);
    void (*set_input_poll)(retro_input_poll_t);
    void (*set_input_state)(retro_input_state_t);
    void (*init)(void);
    void (*deinit)(void);
    unsigned (*api_version)(void);
    void (*get_system_info)(struct retro_system_info *);
    void (*get_system_av_info)(struct retro_system_av_info *);
    bool (*load_game)(const struct retro_game_info *);
    void (*unload_game)(void);
    void (*run)(void);
    void (*set_controller_port_device)(unsigned, unsigned);
    void *(*get_memory_data)(unsigned);
    size_t (*get_memory_size)(unsigned);
};

struct framebuffer {
    int fd;
    struct fb_fix_screeninfo fix;
    struct fb_var_screeninfo var;
    uint8_t *memory;
    size_t size;
};

struct input_device {
    int fd;
    int axis_min[ABS_CNT];
    int axis_max[ABS_CNT];
    int axis_value[ABS_CNT];
    uint8_t axis_valid[ABS_CNT];
};

static struct core_api core;
static struct framebuffer fb = {.fd = -1};
static struct input_device inputs[MAX_INPUTS];
static int input_count;
static uint8_t buttons[RETRO_DEVICE_ID_JOYPAD_R3 + 1];
static snd_pcm_t *pcm;
static enum retro_pixel_format pixel_format = RETRO_PIXEL_FORMAT_RGB565;
static struct retro_system_av_info av_info;
static volatile sig_atomic_t stopping;
static volatile sig_atomic_t power_requested;
static int exit_left_held;
static int exit_right_held;
static int64_t exit_chord_since_ms;
static const struct system_config *active_system;
static const char *core_path = "/usr/lib/guideos/doom/prboom_libretro.so";
static char save_path[PATH_MAX] = "/data/guideos/doom";
static char bios_path[PATH_MAX] = "/data/guideos/doom";
static char ram_path[PATH_MAX];
static unsigned long video_frame_count;

static void stop_handler(int signal_number)
{
    (void)signal_number;
    stopping = 1;
}

static int make_directory(const char *path)
{
    if (mkdir(path, 0755) == 0 || errno == EEXIST) return 0;
    return -1;
}

static int allowed_wad(const char *requested, char *resolved, size_t capacity)
{
    static const char *roots[] = {
        "/data/guide-games/doom/",
        "/media/guide-card/GUIDE/GAMES/DOOM/",
        "/media/guide-card/Guide/Games/Doom/"
    };
    struct stat info;
    const char *suffix;
    unsigned i;
    if (!requested || capacity < PATH_MAX || !realpath(requested, resolved)) return 0;
    suffix = strrchr(resolved, '.');
    if (!suffix || strcasecmp(suffix, ".wad") != 0) return 0;
    if (lstat(resolved, &info) != 0 || !S_ISREG(info.st_mode) || info.st_size <= 0 ||
        info.st_size > (off_t)(1024ULL * 1024ULL * 1024ULL)) return 0;
    for (i = 0; i < sizeof(roots) / sizeof(roots[0]); ++i)
        if (strncmp(resolved, roots[i], strlen(roots[i])) == 0) return 1;
    return 0;
}

static int extension_allowed(const char *path, const char *extensions)
{
    const char *suffix = strrchr(path, '.');
    const char *item = extensions;
    if (!suffix) return 0;
    while (item && *item) {
        const char *end = strchr(item, ',');
        size_t length = end ? (size_t)(end - item) : strlen(item);
        if (strlen(suffix) == length && strncasecmp(suffix, item, length) == 0) return 1;
        item = end ? end + 1 : NULL;
    }
    return 0;
}

static const struct system_config *find_system(const char *id)
{
    unsigned i;
    for (i = 0; i < sizeof(systems) / sizeof(systems[0]); ++i)
        if (strcmp(systems[i].id, id) == 0) return &systems[i];
    return NULL;
}

static int allowed_content(const struct system_config *system, const char *requested,
                           char *resolved, size_t capacity)
{
    char canonical[PATH_MAX], friendly[PATH_MAX];
    struct stat info;
    if (!system || !requested || capacity < PATH_MAX || !realpath(requested, resolved)) return 0;
    if (!extension_allowed(resolved, system->extensions)) return 0;
    if (lstat(resolved, &info) != 0 || !S_ISREG(info.st_mode) || info.st_size <= 0 ||
        info.st_size > (off_t)(8ULL * 1024ULL * 1024ULL * 1024ULL)) return 0;
    snprintf(canonical, sizeof(canonical), "/media/guide-card/GUIDE/GAMES/%s/", system->folder);
    snprintf(friendly, sizeof(friendly), "/media/guide-card/Guide/Games/%s/", system->folder);
    return strncmp(resolved, canonical, strlen(canonical)) == 0 ||
           strncmp(resolved, friendly, strlen(friendly)) == 0;
}

static int prepare_paths(const struct system_config *system, const char *content)
{
    const char *name, *dot;
    size_t stem, prefix;
    if (make_directory("/data/guideos") != 0 ||
        make_directory("/data/guideos/emulation") != 0 ||
        make_directory("/data/guideos/emulation/saves") != 0) return -1;
    snprintf(save_path, sizeof(save_path), "/data/guideos/emulation/saves/%s", system->id);
    if (make_directory(save_path) != 0) return -1;
    snprintf(bios_path, sizeof(bios_path), "/media/guide-card/GUIDE/BIOS/%s", system->bios_folder);
    if (access(bios_path, R_OK) != 0)
        snprintf(bios_path, sizeof(bios_path), "/media/guide-card/Guide/Bios/%s", system->bios_folder);
    name = strrchr(content, '/'); name = name ? name + 1 : content;
    dot = strrchr(name, '.'); stem = dot && dot > name ? (size_t)(dot - name) : strlen(name);
    if (stem > 180) stem = 180;
    prefix = strlen(save_path);
    if (prefix + stem + 6 > sizeof(ram_path)) return -1;
    memcpy(ram_path, save_path, prefix);
    ram_path[prefix++] = '/';
    memcpy(ram_path + prefix, name, stem);
    prefix += stem;
    memcpy(ram_path + prefix, ".srm", 5);
    return 0;
}

static uint32_t pack_channel(uint8_t value, unsigned offset, unsigned length)
{
    uint32_t maximum;
    if (!length) return 0;
    maximum = length >= 32 ? UINT32_MAX : ((1u << length) - 1u);
    return ((uint32_t)value * maximum / 255u) << offset;
}

static uint32_t pack_pixel(uint8_t red, uint8_t green, uint8_t blue)
{
    return pack_channel(red, fb.var.red.offset, fb.var.red.length) |
           pack_channel(green, fb.var.green.offset, fb.var.green.length) |
           pack_channel(blue, fb.var.blue.offset, fb.var.blue.length) |
           pack_channel(255, fb.var.transp.offset, fb.var.transp.length);
}

static void write_pixel(unsigned x, unsigned y, uint32_t value)
{
    uint8_t *destination;
    unsigned bytes = fb.var.bits_per_pixel / 8;
    if (x >= fb.var.xres || y >= fb.var.yres || (bytes != 2 && bytes != 4)) return;
    destination = fb.memory + (size_t)(y + fb.var.yoffset) * fb.fix.line_length +
                  (size_t)(x + fb.var.xoffset) * bytes;
    if (bytes == 4) memcpy(destination, &value, 4);
    else {
        uint16_t short_value = (uint16_t)value;
        memcpy(destination, &short_value, 2);
    }
}

static int framebuffer_open(void)
{
    fb.fd = open("/dev/fb0", O_RDWR | O_CLOEXEC);
    if (fb.fd < 0 || ioctl(fb.fd, FBIOGET_FSCREENINFO, &fb.fix) != 0 ||
        ioctl(fb.fd, FBIOGET_VSCREENINFO, &fb.var) != 0) return -1;
    fb.size = fb.fix.smem_len ? fb.fix.smem_len :
              (size_t)fb.fix.line_length * fb.var.yres_virtual;
    fb.memory = mmap(NULL, fb.size, PROT_READ | PROT_WRITE, MAP_SHARED, fb.fd, 0);
    if (fb.memory == MAP_FAILED) { fb.memory = NULL; return -1; }
    memset(fb.memory, 0, fb.size);
    fprintf(stderr,
            "guide-emulator: framebuffer visible=%ux%u virtual=%ux%u offset=%u,%u bpp=%u stride=%u bytes=%zu rgba=%u/%u,%u/%u,%u/%u,%u/%u\n",
            fb.var.xres, fb.var.yres, fb.var.xres_virtual, fb.var.yres_virtual,
            fb.var.xoffset, fb.var.yoffset, fb.var.bits_per_pixel,
            fb.fix.line_length, fb.size, fb.var.red.offset, fb.var.red.length,
            fb.var.green.offset, fb.var.green.length, fb.var.blue.offset,
            fb.var.blue.length, fb.var.transp.offset, fb.var.transp.length);
    fflush(stderr);
    return 0;
}

static void video_refresh(const void *data, unsigned width, unsigned height, size_t pitch)
{
    unsigned x, y, output_w, output_h, origin_x, origin_y;
    double aspect;
    static unsigned old_w, old_h;
    if (!data || !width || !height || !fb.memory) return;
    if (video_frame_count++ == 0) {
        fprintf(stderr,
                "guide-emulator: first video frame width=%u height=%u pitch=%zu format=%d aspect=%.4f\n",
                width, height, pitch, (int)pixel_format,
                av_info.geometry.aspect_ratio);
        fflush(stderr);
    }
    aspect = av_info.geometry.aspect_ratio > 0.01f ? av_info.geometry.aspect_ratio :
             (double)width / (double)height;
    output_w = fb.var.xres;
    output_h = (unsigned)((double)output_w / aspect + 0.5);
    if (output_h > fb.var.yres) {
        output_h = fb.var.yres;
        output_w = (unsigned)((double)output_h * aspect + 0.5);
    }
    origin_x = (fb.var.xres - output_w) / 2;
    origin_y = (fb.var.yres - output_h) / 2;
    if (old_w != output_w || old_h != output_h) {
        memset(fb.memory, 0, fb.size);
        old_w = output_w; old_h = output_h;
    }
    for (y = 0; y < output_h; ++y) {
        unsigned source_y = (uint64_t)y * height / output_h;
        const uint8_t *row = (const uint8_t *)data + (size_t)source_y * pitch;
        for (x = 0; x < output_w; ++x) {
            unsigned source_x = (uint64_t)x * width / output_w;
            uint8_t red, green, blue;
            if (pixel_format == RETRO_PIXEL_FORMAT_XRGB8888) {
                uint32_t source;
                memcpy(&source, row + source_x * 4, 4);
                red = (uint8_t)(source >> 16); green = (uint8_t)(source >> 8); blue = (uint8_t)source;
            } else if (pixel_format == RETRO_PIXEL_FORMAT_RGB565) {
                uint16_t source;
                memcpy(&source, row + source_x * 2, 2);
                red = (uint8_t)(((source >> 11) & 31) * 255 / 31);
                green = (uint8_t)(((source >> 5) & 63) * 255 / 63);
                blue = (uint8_t)((source & 31) * 255 / 31);
            } else {
                uint16_t source;
                memcpy(&source, row + source_x * 2, 2);
                red = (uint8_t)(((source >> 10) & 31) * 255 / 31);
                green = (uint8_t)(((source >> 5) & 31) * 255 / 31);
                blue = (uint8_t)((source & 31) * 255 / 31);
            }
            write_pixel(origin_x + x, origin_y + y, pack_pixel(red, green, blue));
        }
    }
}

static void audio_sample(int16_t left, int16_t right)
{
    int16_t pair[2] = {left, right};
    if (pcm) (void)snd_pcm_writei(pcm, pair, 1);
}

static size_t audio_batch(const int16_t *data, size_t frames)
{
    snd_pcm_sframes_t written, total = 0;
    if (!pcm) return frames;
    while ((size_t)total < frames && !stopping) {
        written = snd_pcm_writei(pcm, data + total * 2, frames - (size_t)total);
        if (written < 0) {
            if (snd_pcm_recover(pcm, (int)written, 1) < 0) break;
        } else total += written;
    }
    return total < 0 ? 0 : (size_t)total;
}

static void input_open(void)
{
    DIR *directory = opendir("/dev/input");
    struct dirent *entry;
    if (!directory) return;
    while ((entry = readdir(directory)) && input_count < MAX_INPUTS) {
        char path[128];
        int descriptor, axis;
        if (strncmp(entry->d_name, "event", 5) != 0) continue;
        if (strlen(entry->d_name) > 100) continue;
        snprintf(path, sizeof(path), "/dev/input/%s", entry->d_name);
        descriptor = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (descriptor < 0) continue;
        inputs[input_count].fd = descriptor;
        for (axis = 0; axis < ABS_CNT; ++axis) {
            struct input_absinfo info;
            if (ioctl(descriptor, EVIOCGABS(axis), &info) == 0 && info.maximum > info.minimum) {
                inputs[input_count].axis_valid[axis] = 1;
                inputs[input_count].axis_min[axis] = info.minimum;
                inputs[input_count].axis_max[axis] = info.maximum;
                inputs[input_count].axis_value[axis] = info.value;
            }
        }
        ++input_count;
    }
    closedir(directory);
}

static int16_t normalized_axis(unsigned code)
{
    int device;
    for (device = 0; device < input_count; ++device) {
        int minimum, maximum, value;
        if (code >= ABS_CNT || !inputs[device].axis_valid[code]) continue;
        minimum = inputs[device].axis_min[code]; maximum = inputs[device].axis_max[code];
        value = inputs[device].axis_value[code];
        value = (int)(((int64_t)(value - minimum) * 65535) / (maximum - minimum) - 32768);
        if (value > -5000 && value < 5000) value = 0;
        if (value < -32768) value = -32768;
        if (value > 32767) value = 32767;
        return (int16_t)value;
    }
    return 0;
}

static void set_key(unsigned code, int pressed)
{
    switch (code) {
    case KEY_UP: buttons[RETRO_DEVICE_ID_JOYPAD_UP] = pressed; break;
    case KEY_DOWN: buttons[RETRO_DEVICE_ID_JOYPAD_DOWN] = pressed; break;
    case KEY_LEFT: buttons[RETRO_DEVICE_ID_JOYPAD_LEFT] = pressed; break;
    case KEY_RIGHT: buttons[RETRO_DEVICE_ID_JOYPAD_RIGHT] = pressed; break;
    case BTN_SOUTH: buttons[RETRO_DEVICE_ID_JOYPAD_A] = pressed; break;
    case BTN_EAST: buttons[RETRO_DEVICE_ID_JOYPAD_B] = pressed; break;
    case BTN_NORTH: buttons[RETRO_DEVICE_ID_JOYPAD_X] = pressed; break;
    /* The RG35XX H vendor driver reports L1/R1/L2/R2 with the first
     * code in each pair; the second is the standard Linux fallback. */
    case BTN_WEST: buttons[RETRO_DEVICE_ID_JOYPAD_Y] = pressed; break;
    case BTN_TL: buttons[RETRO_DEVICE_ID_JOYPAD_L] = pressed; break;
    case BTN_Z: case BTN_TR: buttons[RETRO_DEVICE_ID_JOYPAD_R] = pressed; break;
    case BTN_SELECT: buttons[RETRO_DEVICE_ID_JOYPAD_SELECT] = pressed; break;
    case BTN_START: buttons[RETRO_DEVICE_ID_JOYPAD_START] = pressed; break;
    case BTN_TL2: buttons[RETRO_DEVICE_ID_JOYPAD_L2] = pressed; break;
    case BTN_TR2: buttons[RETRO_DEVICE_ID_JOYPAD_R2] = pressed; break;
    case BTN_MODE: case KEY_MENU: buttons[RETRO_DEVICE_ID_JOYPAD_START] = pressed; break;
    case KEY_BACK: buttons[RETRO_DEVICE_ID_JOYPAD_SELECT] = pressed; break;
    case BTN_THUMBL: buttons[RETRO_DEVICE_ID_JOYPAD_L3] = pressed; break;
    case BTN_THUMBR: buttons[RETRO_DEVICE_ID_JOYPAD_R3] = pressed; break;
    default: break;
    }
}

static void input_poll(void)
{
    int i;
    struct timespec now;
    int64_t now_ms;
    for (i = 0; i < input_count; ++i) {
        struct input_event event;
        while (read(inputs[i].fd, &event, sizeof(event)) == (ssize_t)sizeof(event)) {
            if (event.type == EV_KEY && event.code == KEY_POWER && event.value == 1) {
                power_requested = 1;
                stopping = 1;
            } else if (event.type == EV_KEY) {
                set_key(event.code, event.value != 0);
                /* The prototype vendor driver has also reported its two
                 * front function keys as BTN_TL/BTN_TR. Accept that pair as
                 * an exit chord only after a deliberate one-second hold. */
                if (event.code == BTN_TL) exit_left_held = event.value != 0;
                if (event.code == BTN_TR) exit_right_held = event.value != 0;
            }
            else if (event.type == EV_ABS && event.code < ABS_CNT)
                inputs[i].axis_value[event.code] = event.value;
        }
    }
    (void)clock_gettime(CLOCK_MONOTONIC, &now);
    now_ms = (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
    if ((buttons[RETRO_DEVICE_ID_JOYPAD_START] &&
         buttons[RETRO_DEVICE_ID_JOYPAD_SELECT]) ||
        (exit_left_held && exit_right_held)) {
        if (!exit_chord_since_ms) exit_chord_since_ms = now_ms;
        else if (now_ms - exit_chord_since_ms >= 1000) stopping = 1;
    } else exit_chord_since_ms = 0;
}

static int16_t input_state(unsigned port, unsigned device, unsigned index, unsigned id)
{
    if (port != 0) return 0;
    if (device == RETRO_DEVICE_JOYPAD && id <= RETRO_DEVICE_ID_JOYPAD_R3) {
        int16_t hat_x = normalized_axis(ABS_HAT0X), hat_y = normalized_axis(ABS_HAT0Y);
        if (id == RETRO_DEVICE_ID_JOYPAD_LEFT && hat_x < -16000) return 1;
        if (id == RETRO_DEVICE_ID_JOYPAD_RIGHT && hat_x > 16000) return 1;
        if (id == RETRO_DEVICE_ID_JOYPAD_UP && hat_y < -16000) return 1;
        if (id == RETRO_DEVICE_ID_JOYPAD_DOWN && hat_y > 16000) return 1;
        return buttons[id];
    }
    if (device == RETRO_DEVICE_ANALOG && index == RETRO_DEVICE_INDEX_ANALOG_LEFT) {
        if (id == RETRO_DEVICE_ID_ANALOG_X) return normalized_axis(ABS_X);
        return normalized_axis(ABS_Y) ? normalized_axis(ABS_Y) : normalized_axis(ABS_Z);
    }
    if (device == RETRO_DEVICE_ANALOG && index == RETRO_DEVICE_INDEX_ANALOG_RIGHT) {
        if (id == RETRO_DEVICE_ID_ANALOG_X) return normalized_axis(ABS_RX);
        return normalized_axis(ABS_RY) ? normalized_axis(ABS_RY) : normalized_axis(ABS_RZ);
    }
    return 0;
}

static const char *option_value(const char *key)
{
    if (!strcmp(key, "prboom-resolution")) return "320x200";
    if (!strcmp(key, "prboom-color_format")) return "16bits";
    if (!strcmp(key, "prboom-sound_samplerate")) return "44100";
    if (!strcmp(key, "prboom-render_threads")) return "OFF";
    if (!strcmp(key, "prboom-mmap_wads")) return "enabled";
    if (!strcmp(key, "prboom-mouse_on")) return "disabled";
    if (!strcmp(key, "prboom-rumble")) return "disabled";
    if (!strcmp(key, "prboom-analog_deadzone")) return "15";
    if (!strcmp(key, "prboom-purge_limit")) return "64";
    return NULL;
}

static bool environment(unsigned command, void *data)
{
    switch (command) {
    case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
        if (*(enum retro_pixel_format *)data == RETRO_PIXEL_FORMAT_0RGB1555 ||
            *(enum retro_pixel_format *)data == RETRO_PIXEL_FORMAT_RGB565 ||
            *(enum retro_pixel_format *)data == RETRO_PIXEL_FORMAT_XRGB8888) {
            pixel_format = *(enum retro_pixel_format *)data; return true;
        }
        return false;
    case RETRO_ENVIRONMENT_GET_CAN_DUPE: *(bool *)data = true; return true;
    case RETRO_ENVIRONMENT_GET_INPUT_BITMASKS: return false;
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_CORE_ASSETS_DIRECTORY:
        *(const char **)data = bios_path; return true;
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:
        *(const char **)data = save_path; return true;
    case RETRO_ENVIRONMENT_GET_VARIABLE: {
        struct retro_variable *variable = data;
        variable->value = option_value(variable->key); return variable->value != NULL;
    }
    case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE: *(bool *)data = false; return true;
    case RETRO_ENVIRONMENT_GET_AUDIO_VIDEO_ENABLE: *(int *)data = 3; return true;
    case RETRO_ENVIRONMENT_SET_GEOMETRY:
        av_info.geometry = *(const struct retro_game_geometry *)data; return true;
    case RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO:
        av_info = *(const struct retro_system_av_info *)data; return true;
    case RETRO_ENVIRONMENT_SHUTDOWN: stopping = 1; return true;
    case RETRO_ENVIRONMENT_SET_VARIABLES:
    case RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS:
    case RETRO_ENVIRONMENT_SET_CONTROLLER_INFO:
    case RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME:
    case RETRO_ENVIRONMENT_SET_PERFORMANCE_LEVEL:
        return true;
    default: return false;
    }
}

static int load_core(void)
{
    void *library = dlopen(core_path, RTLD_NOW | RTLD_LOCAL);
#define LOAD(name) do { *(void **)(&core.name) = dlsym(library, "retro_" #name); if (!core.name) return -1; } while (0)
    if (!library) { fprintf(stderr, "guide-doom: %s\n", dlerror()); return -1; }
    LOAD(set_environment); LOAD(set_video_refresh); LOAD(set_audio_sample);
    LOAD(set_audio_sample_batch); LOAD(set_input_poll); LOAD(set_input_state);
    LOAD(init); LOAD(deinit); LOAD(api_version); LOAD(get_system_info);
    LOAD(get_system_av_info); LOAD(load_game); LOAD(unload_game); LOAD(run);
    LOAD(set_controller_port_device);
    LOAD(get_memory_data); LOAD(get_memory_size);
#undef LOAD
    return core.api_version() == RETRO_API_VERSION ? 0 : -1;
}

static int audio_open(void)
{
    const char *device = getenv("GUIDE_EMULATOR_ALSA_DEVICE");
    if ((!device || !*device) && !active_system) device = getenv("GUIDE_DOOM_ALSA_DEVICE");
    unsigned rate = av_info.timing.sample_rate > 8000.0 ? (unsigned)av_info.timing.sample_rate : 44100;
    if (!device || !*device) device = "default";
    if (snd_pcm_open(&pcm, device, SND_PCM_STREAM_PLAYBACK, 0) < 0) { pcm = NULL; return -1; }
    if (snd_pcm_set_params(pcm, SND_PCM_FORMAT_S16_LE, SND_PCM_ACCESS_RW_INTERLEAVED,
                           2, rate, 1, 50000) < 0) {
        snd_pcm_close(pcm); pcm = NULL; return -1;
    }
    return 0;
}

static void load_battery_save(void)
{
    void *memory = core.get_memory_data(RETRO_MEMORY_SAVE_RAM);
    size_t size = core.get_memory_size(RETRO_MEMORY_SAVE_RAM);
    FILE *input;
    if (!active_system || !memory || !size) return;
    input = fopen(ram_path, "rb");
    if (!input) return;
    (void)fread(memory, 1, size, input);
    fclose(input);
}

static void store_battery_save(void)
{
    void *memory = core.get_memory_data(RETRO_MEMORY_SAVE_RAM);
    size_t size = core.get_memory_size(RETRO_MEMORY_SAVE_RAM);
    FILE *output;
    if (!active_system || !memory || !size) return;
    output = fopen(ram_path, "wb");
    if (!output) return;
    if (fwrite(memory, 1, size, output) != size) fprintf(stderr, "guide-emulator: incomplete save write\n");
    if (fflush(output) == 0) (void)fsync(fileno(output));
    fclose(output);
}

int main(int argc, char **argv)
{
    char content[PATH_MAX];
    struct retro_game_info game = {0};
    struct timespec deadline;
    double frame_ns;
    int i, loaded = 0;
    if (argc == 3) {
        active_system = find_system(argv[1]);
        if (!allowed_content(active_system, argv[2], content, sizeof(content))) {
            fprintf(stderr, "guide-emulator: choose supported content from the selected external Guide folder\n");
            return 2;
        }
        core_path = active_system->core;
        if (prepare_paths(active_system, content) != 0) return 3;
        fprintf(stderr, "guide-emulator: system=%s core=%s content=%s\n",
                active_system->id, core_path, content);
    } else if (argc == 2 && allowed_wad(argv[1], content, sizeof(content))) {
        (void)make_directory("/data/guideos");
        if (make_directory(save_path) != 0) return 3;
    } else {
        fprintf(stderr, "usage: guide-emulator SYSTEM CONTENT\n");
        return 2;
    }
    if (framebuffer_open() != 0 || load_core() != 0) return 3;
    signal(SIGINT, stop_handler); signal(SIGTERM, stop_handler); signal(SIGHUP, stop_handler);
    input_open();
    core.set_environment(environment); core.set_video_refresh(video_refresh);
    core.set_audio_sample(audio_sample); core.set_audio_sample_batch(audio_batch);
    core.set_input_poll(input_poll); core.set_input_state(input_state);
    core.init(); core.get_system_av_info(&av_info);
    (void)audio_open();
    game.path = content;
    if (!core.load_game(&game)) goto done;
    loaded = 1;
    load_battery_save();
    core.get_system_av_info(&av_info);
    core.set_controller_port_device(0, RETRO_DEVICE_JOYPAD);
    frame_ns = av_info.timing.fps > 1.0 ? 1000000000.0 / av_info.timing.fps : 1000000000.0 / 60.0;
    clock_gettime(CLOCK_MONOTONIC, &deadline);
    while (!stopping) {
        core.run();
        deadline.tv_nsec += (long)frame_ns;
        while (deadline.tv_nsec >= 1000000000L) { deadline.tv_nsec -= 1000000000L; ++deadline.tv_sec; }
        (void)clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &deadline, NULL);
    }
done:
    if (loaded) { store_battery_save(); core.unload_game(); }
    core.deinit();
    if (pcm) { snd_pcm_drop(pcm); snd_pcm_close(pcm); }
    for (i = 0; i < input_count; ++i) close(inputs[i].fd);
    if (fb.memory) munmap(fb.memory, fb.size);
    if (fb.fd >= 0) close(fb.fd);
    return power_requested ? GUIDE_SUPERVISOR_POWER_EXIT : loaded ? 0 : 4;
}
