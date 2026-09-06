// SPDX-License-Identifier: AGPL-3.0-or-later

#include <errno.h>
#include <dirent.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

#include "cartridge.h"
#include "installer.h"
#include "wifi.h"

#define LOGO_WIDTH 256u
#define LOGO_HEIGHT 256u
#define LOGO_PATH "/usr/share/guideos/guide-globe-emblem-256.rgba"
#define ROSE_WIDTH 250u
#define ROSE_HEIGHT 250u
#define ROSE_PATH "/usr/share/guideos/guide-rose-seal-250.rgba"
#define MAX_INPUTS 16
#define LAST_KNOWN_TIME "/var/lib/guideos/last-known-time"

struct glyph { char letter; uint8_t rows[7]; };

static const struct glyph font[] = {
    {' ', {0, 0, 0, 0, 0, 0, 0}}, {'\'', {0x0c, 0x0c, 0x08, 0, 0, 0, 0}},
    {'!', {0x04,0x04,0x04,0x04,0x04,0,0x04}}, {'"', {0x0a,0x0a,0x0a,0,0,0,0}},
    {'#', {0x0a,0x1f,0x0a,0x0a,0x1f,0x0a,0}}, {'$', {0x04,0x0f,0x14,0x0e,0x05,0x1e,0x04}},
    {'%', {0x19,0x1a,0x04,0x08,0x0b,0x13,0}}, {'&', {0x0c,0x12,0x14,0x08,0x15,0x12,0x0d}},
    {'(', {0x02,0x04,0x08,0x08,0x08,0x04,0x02}}, {')', {0x08,0x04,0x02,0x02,0x02,0x04,0x08}},
    {'*', {0,0x15,0x0e,0x1f,0x0e,0x15,0}}, {'+', {0,0x04,0x04,0x1f,0x04,0x04,0}},
    {',', {0,0,0,0,0,0x0c,0x08}}, {'-', {0, 0, 0, 0x1f, 0, 0, 0}},
    {'.', {0, 0, 0, 0, 0, 0x0c, 0x0c}}, {':', {0, 0x0c, 0x0c, 0, 0x0c, 0x0c, 0}},
    {'/', {0x01,0x02,0x04,0x08,0x10,0,0}}, {';', {0,0x0c,0x0c,0,0x0c,0x08,0x10}},
    {'<', {0x02,0x04,0x08,0x10,0x08,0x04,0x02}}, {'=', {0,0,0x1f,0,0x1f,0,0}},
    {'>', {0x08,0x04,0x02,0x01,0x02,0x04,0x08}}, {'?', {0x0e,0x11,0x01,0x02,0x04,0,0x04}},
    {'@', {0x0e,0x11,0x17,0x15,0x17,0x10,0x0e}},
    {'[', {0x0e,0x08,0x08,0x08,0x08,0x08,0x0e}}, {'\\', {0x10,0x08,0x04,0x02,0x01,0,0}},
    {']', {0x0e,0x02,0x02,0x02,0x02,0x02,0x0e}}, {'^', {0x04,0x0a,0x11,0,0,0,0}},
    {'_', {0,0,0,0,0,0,0x1f}}, {'`', {0x08,0x04,0x02,0,0,0,0}},
    {'{', {0x03,0x04,0x04,0x08,0x04,0x04,0x03}}, {'|', {0x04,0x04,0x04,0x04,0x04,0x04,0x04}},
    {'}', {0x18,0x04,0x04,0x02,0x04,0x04,0x18}}, {'~', {0,0,0x09,0x16,0,0,0}},
    {'0', {0x0e, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0e}}, {'1', {0x04, 0x0c, 0x14, 0x04, 0x04, 0x04, 0x1f}},
    {'2', {0x0e, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1f}}, {'3', {0x1e, 0x01, 0x01, 0x0e, 0x01, 0x01, 0x1e}},
    {'4', {0x02, 0x06, 0x0a, 0x12, 0x1f, 0x02, 0x02}}, {'5', {0x1f, 0x10, 0x10, 0x1e, 0x01, 0x01, 0x1e}},
    {'6', {0x0e, 0x10, 0x10, 0x1e, 0x11, 0x11, 0x0e}}, {'7', {0x1f, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08}},
    {'8', {0x0e, 0x11, 0x11, 0x0e, 0x11, 0x11, 0x0e}}, {'9', {0x0e, 0x11, 0x11, 0x0f, 0x01, 0x01, 0x0e}},
    {'A', {0x0e, 0x11, 0x11, 0x1f, 0x11, 0x11, 0x11}}, {'B', {0x1e, 0x11, 0x11, 0x1e, 0x11, 0x11, 0x1e}},
    {'C', {0x0f, 0x10, 0x10, 0x10, 0x10, 0x10, 0x0f}}, {'D', {0x1e, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1e}},
    {'E', {0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x1f}}, {'F', {0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x10}},
    {'G', {0x0f, 0x10, 0x10, 0x17, 0x11, 0x11, 0x0f}}, {'H', {0x11, 0x11, 0x11, 0x1f, 0x11, 0x11, 0x11}},
    {'I', {0x1f, 0x04, 0x04, 0x04, 0x04, 0x04, 0x1f}}, {'J', {0x07, 0x02, 0x02, 0x02, 0x12, 0x12, 0x0c}},
    {'K', {0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11}}, {'L', {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1f}},
    {'M', {0x11, 0x1b, 0x15, 0x15, 0x11, 0x11, 0x11}}, {'N', {0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11}},
    {'O', {0x0e, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e}}, {'P', {0x1e, 0x11, 0x11, 0x1e, 0x10, 0x10, 0x10}},
    {'Q', {0x0e, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0d}}, {'R', {0x1e, 0x11, 0x11, 0x1e, 0x14, 0x12, 0x11}},
    {'S', {0x0f, 0x10, 0x10, 0x0e, 0x01, 0x01, 0x1e}}, {'T', {0x1f, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04}},
    {'U', {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e}}, {'V', {0x11, 0x11, 0x11, 0x11, 0x11, 0x0a, 0x04}},
    {'W', {0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0a}}, {'X', {0x11, 0x11, 0x0a, 0x04, 0x0a, 0x11, 0x11}},
    {'Y', {0x11, 0x11, 0x0a, 0x04, 0x04, 0x04, 0x04}}, {'Z', {0x1f, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1f}},
    {'a', {0,0,0x0e,0x01,0x0f,0x11,0x0f}}, {'b', {0x10,0x10,0x1e,0x11,0x11,0x11,0x1e}},
    {'c', {0,0,0x0e,0x11,0x10,0x11,0x0e}}, {'d', {0x01,0x01,0x0f,0x11,0x11,0x11,0x0f}},
    {'e', {0,0,0x0e,0x11,0x1f,0x10,0x0e}}, {'f', {0x06,0x08,0x1c,0x08,0x08,0x08,0x08}},
    {'g', {0,0,0x0f,0x11,0x0f,0x01,0x0e}}, {'h', {0x10,0x10,0x1e,0x11,0x11,0x11,0x11}},
    {'i', {0x04,0,0x0c,0x04,0x04,0x04,0x0e}}, {'j', {0x02,0,0x06,0x02,0x02,0x12,0x0c}},
    {'k', {0x10,0x10,0x12,0x14,0x18,0x14,0x12}}, {'l', {0x0c,0x04,0x04,0x04,0x04,0x04,0x0e}},
    {'m', {0,0,0x1a,0x15,0x15,0x15,0x15}}, {'n', {0,0,0x1e,0x11,0x11,0x11,0x11}},
    {'o', {0,0,0x0e,0x11,0x11,0x11,0x0e}}, {'p', {0,0,0x1e,0x11,0x1e,0x10,0x10}},
    {'q', {0,0,0x0f,0x11,0x0f,0x01,0x01}}, {'r', {0,0,0x16,0x19,0x10,0x10,0x10}},
    {'s', {0,0,0x0f,0x10,0x0e,0x01,0x1e}}, {'t', {0x08,0x08,0x1c,0x08,0x08,0x09,0x06}},
    {'u', {0,0,0x11,0x11,0x11,0x13,0x0d}}, {'v', {0,0,0x11,0x11,0x11,0x0a,0x04}},
    {'w', {0,0,0x11,0x11,0x15,0x15,0x0a}}, {'x', {0,0,0x11,0x0a,0x04,0x0a,0x11}},
    {'y', {0,0,0x11,0x11,0x0f,0x01,0x0e}}, {'z', {0,0,0x1f,0x02,0x04,0x08,0x1f}},
};

struct framebuffer {
    int fd;
    struct fb_fix_screeninfo fix;
    struct fb_var_screeninfo var;
    uint8_t *memory;
    size_t size;
};

struct axis_profile {
    int supported;
    int minimum;
    int maximum;
    int flat;
    int direction;
    int repeat_action;
    int64_t repeat_at_ms;
    unsigned repeats_left;
};

struct input_set {
    struct pollfd pollfds[MAX_INPUTS];
    struct axis_profile axes[MAX_INPUTS][ABS_CNT];
    int count;
};

static void restore_clock_floor(void)
{
    struct timespec now;
    struct stat shell_info;
    time_t floor = 1577836800;
    FILE *saved;
    long long recorded = 0;
    if (stat("/init", &shell_info) == 0 && shell_info.st_mtime > floor)
        floor = shell_info.st_mtime;
    saved = fopen(LAST_KNOWN_TIME, "r");
    if (saved) {
        if (fscanf(saved, "%lld", &recorded) == 1 && recorded > (long long)floor)
            floor = (time_t)recorded;
        fclose(saved);
    }
    if (clock_gettime(CLOCK_REALTIME, &now) == 0 && now.tv_sec < floor) {
        now.tv_sec = floor; now.tv_nsec = 0;
        (void)clock_settime(CLOCK_REALTIME, &now);
    }
}

static void record_clock_floor(FILE *log)
{
    struct timespec now;
    int descriptor;
    char value[32];
    int length;
    if (clock_gettime(CLOCK_REALTIME, &now) != 0) return;
    descriptor = open(LAST_KNOWN_TIME ".new",
                      O_WRONLY | O_CREAT | O_TRUNC | O_NOFOLLOW, 0600);
    if (descriptor < 0) return;
    length = snprintf(value, sizeof(value), "%lld\n", (long long)now.tv_sec);
    if (length > 0 && write(descriptor, value, (size_t)length) == length &&
        fsync(descriptor) == 0) {
        close(descriptor);
        if (rename(LAST_KNOWN_TIME ".new", LAST_KNOWN_TIME) == 0) {
            fprintf(log, "clock floor saved epoch=%lld\n", (long long)now.tv_sec);
            fflush(log); return;
        }
    } else close(descriptor);
    unlink(LAST_KNOWN_TIME ".new");
}
enum action {
    ACTION_NONE,
    ACTION_UP,
    ACTION_DOWN,
    ACTION_LEFT,
    ACTION_RIGHT,
    ACTION_OPEN,
    ACTION_BACK,
    ACTION_SPACE,
    ACTION_POWER,
    ACTION_VOLUME_DOWN,
    ACTION_VOLUME_UP,
    ACTION_L1,
    ACTION_R1,
    ACTION_L2,
    ACTION_R2,
    ACTION_OTHER
};
enum screen {
    SCREEN_MENU,
    SCREEN_WIFI_LIST,
    SCREEN_WIFI_KEYBOARD,
    SCREEN_WIFI_RESULT,
    SCREEN_NODE_LIST,
    SCREEN_NODE_PAIR,
    SCREEN_NODE_RESULT,
    SCREEN_MEDIA_LIST,
    SCREEN_MEDIA_PLAYING,
    SCREEN_MEDIA_SUBTITLES,
    SCREEN_CARTRIDGE_LIST,
    SCREEN_CARTRIDGE_DETAIL,
    SCREEN_INSTALL_CONFIRM,
    SCREEN_INSTALL_RESULT,
    SCREEN_DEVELOPER_LINK,
    SCREEN_WIKIPEDIA_HOME,
    SCREEN_WIKIPEDIA_KEYBOARD,
    SCREEN_WIKIPEDIA_RESULTS,
    SCREEN_WIKIPEDIA_ARTICLE,
    SCREEN_WIKIPEDIA_LINKS,
    SCREEN_DISPLAY,
    SCREEN_INPUT,
    SCREEN_SYSTEM,
    SCREEN_SHUTDOWN
};

struct wifi_ui {
    struct guide_wifi_list list;
    unsigned page;
    unsigned cursor;
    char password[GUIDE_WIFI_PASSWORD_MAX + 1];
    size_t password_length;
    char result[96];
    int success;
};

#define GUIDE_NODE_MAX 8
#define GUIDE_MEDIA_MAX 100
#define GUIDE_SUBTITLE_MAX 8
#define GUIDE_NODE_APP_DIR "/usr/lib/guideos/node-link"
#define GUIDE_MEDIA_DIR "/usr/lib/guideos/media"
#define GUIDE_AUDIO_CONTROL GUIDE_MEDIA_DIR "/bin/guide-audio-control"
#define GUIDE_MEDIA_LOADER GUIDE_MEDIA_DIR "/lib/ld-linux-aarch64.so.1"

static int guide_volume_percent = -1;

struct node_candidate {
    char name[65];
    int trusted;
};

struct media_item {
    char name[121];
    char kind[6];
    unsigned long long size;
    unsigned subtitle_count;
    char subtitles[GUIDE_SUBTITLE_MAX][33];
};

struct node_ui {
    struct node_candidate candidates[GUIDE_NODE_MAX];
    unsigned count;
    unsigned selected;
    unsigned keypad;
    char code[7];
    size_t code_length;
    char message[96];
    char paired_name[65];
    char android_state[33];
    struct media_item media[GUIDE_MEDIA_MAX];
    unsigned media_count;
    unsigned media_total;
    unsigned media_selected;
    pid_t playback_pid;
    int playback_paused;
    unsigned subtitle_menu_selected;
    int subtitle_current;
    int subtitle_resume_after_menu;
    int trusted;
    int success;
};

#define GUIDE_WIKI_QUERY_MAX 80
#define GUIDE_WIKI_TEXT_MAX (6u * 1024u * 1024u)
#define GUIDE_WIKI_PAGE_MAX 16384
#define GUIDE_WIKI_RESULT_MAX 8
#define GUIDE_WIKI_LINK_MAX 500
#define GUIDE_WIKI_PROTOCOL_MARGIN (192u * 1024u)
#define GUIDE_WIKI_APP_DIR "/usr/lib/guideos/apps/wikipedia-0.3"

struct wikipedia_result {
    char title[301];
    unsigned word_count;
};

struct wikipedia_link {
    char title[301];
};

struct wikipedia_ui {
    unsigned keyboard_page;
    unsigned cursor;
    char query[GUIDE_WIKI_QUERY_MAX + 1];
    size_t query_length;
    struct wikipedia_result results[GUIDE_WIKI_RESULT_MAX];
    unsigned result_count;
    unsigned selected_result;
    char title[301];
    char *text;
    size_t text_length;
    size_t page_offsets[GUIDE_WIKI_PAGE_MAX];
    unsigned page;
    unsigned known_pages;
    size_t visible_end;
    struct wikipedia_link links[GUIDE_WIKI_LINK_MAX];
    unsigned link_count;
    unsigned selected_link;
    char message[96];
};

static const uint8_t *glyph_rows(char letter)
{
    size_t i;
    for (i = 0; i < sizeof(font) / sizeof(font[0]); ++i)
        if (font[i].letter == letter) return font[i].rows;
    return font[0].rows;
}

static uint32_t channel(unsigned value, struct fb_bitfield field)
{
    uint64_t maximum;
    if (field.length == 0) return 0;
    maximum = ((uint64_t)1 << field.length) - 1;
    return (uint32_t)(((value * maximum + 127) / 255) << field.offset);
}

static uint32_t color(const struct framebuffer *fb, unsigned r, unsigned g, unsigned b)
{
    /* Translate the original high-contrast palette into the paper-and-ink theme.
     * Keeping the mapping here makes every existing screen inherit the theme,
     * including transient connection, installation, and shutdown states. */
    if (r == 244 && g == 241 && b == 228) { r = 58;  g = 59;  b = 48;  }
    else if (r == 151 && g == 220 && b == 231) { r = 68;  g = 100; b = 112; }
    else if (r == 51 && g == 142 && b == 232)  { r = 72;  g = 111; b = 123; }
    else if (r == 104 && g == 207 && b == 72)  { r = 65;  g = 111; b = 75;  }
    else if (r == 245 && g == 177 && b == 52)  { r = 157; g = 78;  b = 34;  }
    else if (r == 220 && g == 73 && b == 73)   { r = 151; g = 57;  b = 48;  }
    else if (r == 30 && g == 27 && b == 19)    { r = 219; g = 216; b = 201; }
    else if (r == 42 && g == 74 && b == 82)    { r = 104; g = 108; b = 96;  }
    return channel(r, fb->var.red) | channel(g, fb->var.green) |
           channel(b, fb->var.blue) | channel(255, fb->var.transp);
}

static void put_pixel(struct framebuffer *fb, unsigned x, unsigned y, uint32_t pixel)
{
    unsigned bytes = fb->var.bits_per_pixel / 8, i;
    size_t offset;
    if (x >= fb->var.xres || y >= fb->var.yres) return;
    offset = (size_t)(y + fb->var.yoffset) * fb->fix.line_length +
             (size_t)(x + fb->var.xoffset) * bytes;
    for (i = 0; i < bytes; ++i) fb->memory[offset + i] = (uint8_t)(pixel >> (i * 8));
}

static void fill_rect(struct framebuffer *fb, unsigned x, unsigned y,
                      unsigned width, unsigned height, uint32_t pixel)
{
    unsigned dx, dy;
    for (dy = 0; dy < height; ++dy)
        for (dx = 0; dx < width; ++dx) put_pixel(fb, x + dx, y + dy, pixel);
}

static void draw_rect(struct framebuffer *fb, unsigned x, unsigned y,
                      unsigned width, unsigned height, uint32_t pixel)
{
    if (!width || !height) return;
    fill_rect(fb, x, y, width, 1, pixel);
    fill_rect(fb, x, y + height - 1, width, 1, pixel);
    fill_rect(fb, x, y, 1, height, pixel);
    fill_rect(fb, x + width - 1, y, 1, height, pixel);
}

static unsigned text_width(const char *text, unsigned scale)
{
    size_t length = strlen(text);
    return length ? (unsigned)(length * 6 - 1) * scale : 0;
}

static void draw_text(struct framebuffer *fb, unsigned x, unsigned y,
                      const char *text, unsigned scale, uint32_t pixel)
{
    size_t c;
    for (c = 0; text[c]; ++c) {
        const uint8_t *rows = glyph_rows(text[c]);
        unsigned row, column, dx, dy;
        for (row = 0; row < 7; ++row) for (column = 0; column < 5; ++column) {
            if (!(rows[row] & (1u << (4 - column)))) continue;
            for (dy = 0; dy < scale; ++dy) for (dx = 0; dx < scale; ++dx)
                put_pixel(fb, x + (unsigned)c * 6 * scale + column * scale + dx,
                          y + row * scale + dy, pixel);
        }
    }
}

static void draw_centered(struct framebuffer *fb, unsigned y, const char *text,
                          unsigned scale, uint32_t pixel)
{
    unsigned width = text_width(text, scale);
    draw_text(fb, width < fb->var.xres ? (fb->var.xres - width) / 2 : 0,
              y, text, scale, pixel);
}

static void uppercase_line(char *destination, size_t capacity, const char *source)
{
    size_t index;
    if (capacity == 0) return;
    for (index = 0; index + 1 < capacity && source[index]; ++index) {
        unsigned char value = (unsigned char)source[index];
        if (value >= 'a' && value <= 'z') value = (unsigned char)(value - 'a' + 'A');
        if (!(value == ' ' || value == '-' || value == '.' || value == ':' ||
              (value >= '0' && value <= '9') || (value >= 'A' && value <= 'Z'))) value = ' ';
        destination[index] = (char)value;
    }
    destination[index] = '\0';
}

static void draw_diamond(struct framebuffer *fb, unsigned cx, unsigned cy,
                         unsigned radius, uint32_t pixel)
{
    unsigned dy;
    for (dy = 0; dy <= radius * 2; ++dy) {
        unsigned distance = dy > radius ? dy - radius : radius - dy;
        unsigned half = radius - distance;
        fill_rect(fb, cx - half, cy - radius + dy, half * 2 + 1, 1, pixel);
    }
}

static void clear_screen(struct framebuffer *fb)
{
    fill_rect(fb, 0, 0, fb->var.xres, fb->var.yres, color(fb, 239, 237, 225));
}
static void present(struct framebuffer *fb) { (void)msync(fb->memory, fb->size, MS_SYNC); }

static int open_framebuffer(struct framebuffer *fb, FILE *log)
{
    unsigned index;
    memset(fb, 0, sizeof(*fb)); fb->fd = -1;
    for (index = 0; index < 4; ++index) {
        char path[32];
        snprintf(path, sizeof(path), "/dev/fb%u", index);
        fb->fd = open(path, O_RDWR);
        if (fb->fd < 0) continue;
        if (ioctl(fb->fd, FBIOGET_FSCREENINFO, &fb->fix) == 0 &&
            ioctl(fb->fd, FBIOGET_VSCREENINFO, &fb->var) == 0 &&
            (fb->var.bits_per_pixel == 16 || fb->var.bits_per_pixel == 24 || fb->var.bits_per_pixel == 32)) {
            fb->size = fb->fix.smem_len ? fb->fix.smem_len : (size_t)fb->fix.line_length * fb->var.yres_virtual;
            fb->memory = mmap(NULL, fb->size, PROT_READ | PROT_WRITE, MAP_SHARED, fb->fd, 0);
            if (fb->memory != MAP_FAILED) {
                fprintf(log, "framebuffer=%s id=%s size=%ux%u bpp=%u\n", path, fb->fix.id,
                        fb->var.xres, fb->var.yres, fb->var.bits_per_pixel);
                return 0;
            }
        }
        close(fb->fd); fb->fd = -1;
    }
    fprintf(log, "no usable framebuffer: %s\n", strerror(errno));
    return -1;
}

static void close_framebuffer(struct framebuffer *fb)
{
    if (fb->memory && fb->memory != MAP_FAILED) munmap(fb->memory, fb->size);
    if (fb->fd >= 0) close(fb->fd);
}

static int draw_rgba_asset(struct framebuffer *fb, const char *path,
                           unsigned width, unsigned height,
                           unsigned start_x, unsigned start_y, FILE *log)
{
    size_t size = (size_t)width * height * 4;
    uint8_t *rgba = malloc(size);
    FILE *source;
    unsigned x, y;
    if (!rgba) return -1;
    source = fopen(path, "rb");
    if (!source || fread(rgba, 1, size, source) != size) {
        fprintf(log, "art asset unavailable: %s: %s\n", path, strerror(errno));
        if (source) fclose(source);
        free(rgba); return -1;
    }
    fclose(source);
    for (y = 0; y < height; ++y) for (x = 0; x < width; ++x) {
        size_t offset = ((size_t)y * width + x) * 4;
        unsigned alpha = rgba[offset + 3];
        if (alpha) put_pixel(fb, start_x + x, start_y + y,
                             color(fb, (rgba[offset] * alpha + 239 * (255 - alpha)) / 255,
                                   (rgba[offset + 1] * alpha + 237 * (255 - alpha)) / 255,
                                   (rgba[offset + 2] * alpha + 225 * (255 - alpha)) / 255));
    }
    free(rgba); return 0;
}

static int draw_logo(struct framebuffer *fb, unsigned start_y, FILE *log)
{
    unsigned start_x = fb->var.xres > LOGO_WIDTH ? (fb->var.xres - LOGO_WIDTH) / 2 : 0;
    return draw_rgba_asset(fb, LOGO_PATH, LOGO_WIDTH, LOGO_HEIGHT,
                           start_x, start_y, log);
}

static void draw_welcome(struct framebuffer *fb, FILE *log)
{
    clear_screen(fb);
    (void)draw_logo(fb, 20, log);
    draw_centered(fb, 310, "DON'T PANIC", 6, color(fb, 244, 241, 228));
    draw_centered(fb, 382, "GUIDEOS DECK PROTOTYPE", 2, color(fb, 151, 220, 231));
    present(fb);
}

static const char *friendly_title(const char *title)
{
    if (strcmp(title, "WIFI") == 0) return "Wi-Fi";
    if (strcmp(title, "WIFI PASSWORD") == 0) return "Wi-Fi Password";
    if (strcmp(title, "WIFI RESULT") == 0) return "Wi-Fi Result";
    if (strcmp(title, "NODES") == 0) return "Nodes";
    if (strcmp(title, "NODE PAIRING") == 0) return "Node Pairing";
    if (strcmp(title, "NODE LINK") == 0) return "Node Link";
    if (strcmp(title, "WIKIPEDIA") == 0) return "Wikipedia";
    if (strcmp(title, "WIKIPEDIA SEARCH") == 0) return "Wikipedia Search";
    if (strcmp(title, "WIKIPEDIA RESULTS") == 0) return "Wikipedia Results";
    if (strcmp(title, "CARTRIDGES") == 0) return "Cartridges";
    if (strcmp(title, "CARTRIDGE") == 0) return "Cartridge";
    if (strcmp(title, "DEVELOPER LINK") == 0) return "Developer Link";
    if (strcmp(title, "DISPLAY") == 0) return "Display";
    if (strcmp(title, "INPUT") == 0) return "Input";
    if (strcmp(title, "SYSTEM") == 0) return "System";
    if (strcmp(title, "INSTALL") == 0) return "Install";
    if (strcmp(title, "POWER") == 0) return "Power";
    return title;
}

static int read_battery_percent(void)
{
    FILE *file = fopen("/sys/class/power_supply/axp2202-battery/capacity", "r");
    int value = -1;
    if (file) {
        if (fscanf(file, "%d", &value) != 1) value = -1;
        fclose(file);
    }
    return value >= 0 && value <= 100 ? value : -1;
}

static void draw_speaker_icon(struct framebuffer *fb, unsigned x, unsigned y,
                              uint32_t shade)
{
    fill_rect(fb, x, y + 4, 4, 6, shade);
    fill_rect(fb, x + 4, y + 2, 3, 10, shade);
    fill_rect(fb, x + 8, y + 5, 2, 4, shade);
    fill_rect(fb, x + 11, y + 3, 2, 8, shade);
}

static void draw_battery_icon(struct framebuffer *fb, unsigned x, unsigned y,
                              int percent, uint32_t shade)
{
    unsigned fill = percent > 0 ? (unsigned)percent * 14 / 100 : 0;
    fill_rect(fb, x, y, 18, 2, shade);
    fill_rect(fb, x, y + 8, 18, 2, shade);
    fill_rect(fb, x, y + 2, 2, 6, shade);
    fill_rect(fb, x + 16, y + 2, 2, 6, shade);
    fill_rect(fb, x + 18, y + 3, 2, 4, shade);
    if (fill) fill_rect(fb, x + 2, y + 2, fill, 6, shade);
}

static long long monotonic_milliseconds(void)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return 0;
    return (long long)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static void draw_volume_indicator(struct framebuffer *fb, int percent)
{
    char label[32];
    unsigned width = fb->var.xres > 360 ? 360 : fb->var.xres;
    unsigned x = (fb->var.xres - width) / 2;
    unsigned y = fb->var.yres > 112 ? (fb->var.yres - 112) / 2 : 0;
    unsigned bar_x = x + 82, bar_width = width > 118 ? width - 118 : 0;
    uint32_t panel = color(fb, 13, 25, 29);
    uint32_t bright = color(fb, 244, 241, 228);
    uint32_t accent = color(fb, 151, 220, 231);
    if (percent < 0) percent = 0;
    if (percent > 100) percent = 100;
    fill_rect(fb, x, y, width, 112, panel);
    fill_rect(fb, x, y, width, 2, accent);
    fill_rect(fb, x, y + 110, width, 2, accent);
    draw_speaker_icon(fb, x + 28, y + 30, accent);
    (void)snprintf(label, sizeof(label), "Volume %d%%", percent);
    draw_text(fb, x + 82, y + 22, label, 2, bright);
    fill_rect(fb, bar_x, y + 69, bar_width, 10, color(fb, 42, 74, 82));
    if (percent)
        fill_rect(fb, bar_x, y + 69, bar_width * (unsigned)percent / 100, 10, accent);
    present(fb);
}

static void draw_header(struct framebuffer *fb, const char *title)
{
    const char *network = guide_wifi_link_up() ? "Online" : "Offline";
    uint32_t network_color = guide_wifi_link_up() ? color(fb, 104, 207, 72) :
                                                    color(fb, 245, 177, 52);
    int battery_percent = read_battery_percent();
    char battery[8], volume[8];
    unsigned right = fb->var.xres > 28 ? fb->var.xres - 28 : 0;
    unsigned battery_width, volume_width, battery_x, volume_x, network_width, network_x;
    uint32_t battery_color = battery_percent < 0 ? color(fb, 125, 132, 132) :
        battery_percent <= 15 ? color(fb, 220, 73, 73) :
        battery_percent <= 35 ? color(fb, 245, 177, 52) : color(fb, 104, 207, 72);
    (void)snprintf(battery, sizeof(battery), battery_percent < 0 ? "--%%" : "%d%%",
                   battery_percent);
    (void)snprintf(volume, sizeof(volume), guide_volume_percent < 0 ? "--%%" : "%d%%",
                   guide_volume_percent);
    battery_width = text_width(battery, 1) + 26;
    volume_width = text_width(volume, 1) + 19;
    battery_x = right > battery_width ? right - battery_width : 0;
    volume_x = battery_x > volume_width + 12 ? battery_x - volume_width - 12 : 0;
    network_width = text_width(network, 1);
    network_x = volume_x > network_width + 14 ? volume_x - network_width - 14 : 0;
    clear_screen(fb);
    draw_text(fb, 28, 12, "The Guide", 3, color(fb, 244, 241, 228));
    draw_text(fb, 30, 43, "Don't Panic.", 1, color(fb, 151, 220, 231));
    draw_text(fb, network_x, 10, network, 1, network_color);
    draw_speaker_icon(fb, volume_x, 9, color(fb, 151, 220, 231));
    draw_text(fb, volume_x + 17, 10, volume, 1, color(fb, 244, 241, 228));
    draw_text(fb, battery_x, 10, battery, 1, battery_color);
    draw_battery_icon(fb, battery_x + text_width(battery, 1) + 5, 10,
                      battery_percent < 0 ? 0 : battery_percent, battery_color);
    draw_text(fb, fb->var.xres > 220 ? fb->var.xres - 220 : 0, 36,
              friendly_title(title), 2,
              color(fb, 244, 241, 228));
    fill_rect(fb, 20, 66, fb->var.xres > 40 ? fb->var.xres - 40 : 0, 1,
              color(fb, 42, 74, 82));
}

static void draw_footer(struct framebuffer *fb, const char *left, const char *right)
{
    unsigned rw = text_width(right, 2);
    fill_rect(fb, 20, fb->var.yres - 62, fb->var.xres - 40, 1, color(fb, 42, 74, 82));
    draw_text(fb, 36, fb->var.yres - 40, left, 2, color(fb, 151, 220, 231));
    draw_text(fb, fb->var.xres - rw - 36, fb->var.yres - 40, right, 2, color(fb, 244, 241, 228));
}

static void draw_footer_three(struct framebuffer *fb, const char *left,
                              const char *center, const char *right)
{
    unsigned cw = text_width(center, 2), rw = text_width(right, 2);
    fill_rect(fb, 20, fb->var.yres - 62, fb->var.xres - 40, 1, color(fb, 42, 74, 82));
    draw_text(fb, 30, fb->var.yres - 40, left, 2, color(fb, 151, 220, 231));
    draw_text(fb, cw < fb->var.xres ? (fb->var.xres - cw) / 2 : 0,
              fb->var.yres - 40, center, 2, color(fb, 244, 241, 228));
    draw_text(fb, fb->var.xres - rw - 30, fb->var.yres - 40, right, 2,
              color(fb, 245, 177, 52));
}

static void draw_scrollbar(struct framebuffer *fb, unsigned x, unsigned y,
                           unsigned height, unsigned total, unsigned first,
                           unsigned visible)
{
    unsigned thumb_height, thumb_y, travel;
    uint32_t rail = color(fb, 42, 74, 82), thumb = color(fb, 245, 177, 52);
    fill_rect(fb, x, y, 2, height, rail);
    if (!total || total <= visible) {
        fill_rect(fb, x - 2, y, 6, height, thumb);
        return;
    }
    thumb_height = height * visible / total;
    if (thumb_height < 18) thumb_height = 18;
    travel = height - thumb_height;
    thumb_y = y + travel * first / (total - visible);
    fill_rect(fb, x - 2, thumb_y, 6, thumb_height, thumb);
}

static void draw_menu(struct framebuffer *fb, unsigned selected)
{
    static const char *items[] = {"Cartridges", "Wi-Fi", "Nodes", "Media", "Wikipedia",
                                  "Developer Link", "Display Test", "Input Test", "System Info"};
    unsigned row, first = selected > 2 ? selected - 2 : 0;
    char number[4];
    if (first + 5 > 9) first = 4;
    draw_header(fb, "Home");
    for (row = 0; row < 5; ++row) {
        unsigned index = first + row, y = 92 + row * 59;
        uint32_t ink = color(fb, 244, 241, 228);
        snprintf(number, sizeof(number), "%02u", index + 1);
        if (index == selected) {
            fill_rect(fb, 71, y - 10, 284, 42, color(fb, 30, 27, 19));
            fill_rect(fb, 71, y - 10, 4, 42, color(fb, 245, 177, 52));
            ink = color(fb, 245, 177, 52);
        }
        draw_rect(fb, 71, y - 10, 284, 42, color(fb, 42, 74, 82));
        draw_text(fb, 88, y, number, 2, ink);
        draw_text(fb, 132, y, items[index], 2, ink);
    }
    draw_scrollbar(fb, 48, 82, 275, 9, first, 5);
    (void)draw_rgba_asset(fb, ROSE_PATH, ROSE_WIDTH, ROSE_HEIGHT, 380, 96, stderr);
    draw_footer_three(fb, "+ Move", "(A) Open", "(B) Back"); present(fb);
}

static void draw_display_test(struct framebuffer *fb)
{
    static const unsigned bars[][3] = {{245,177,52},{151,220,231},{51,142,232},{104,207,72},{244,241,228},{220,73,73}};
    unsigned i, width;
    draw_header(fb, "DISPLAY");
    draw_centered(fb, 92, "DISPLAY TEST", 4, color(fb, 244, 241, 228));
    width = (fb->var.xres - 80) / 6;
    for (i = 0; i < 6; ++i) fill_rect(fb, 40 + i * width, 170, width, 150,
                                      color(fb, bars[i][0], bars[i][1], bars[i][2]));
    draw_centered(fb, 344, "COLOR AND FRAMEBUFFER", 2, color(fb, 151, 220, 231));
    draw_footer(fb, "TEST 01", "B BACK"); present(fb);
}

static const char *input_name(unsigned type, unsigned code)
{
    if (type == EV_ABS) {
        if (code == ABS_X || code == ABS_Y) return "LEFT STICK X";
        if (code == ABS_Z) return "LEFT STICK Y";
        if (code == ABS_RX || code == ABS_RY) return "RIGHT STICK X";
        if (code == ABS_RZ) return "RIGHT STICK Y";
        if (code == ABS_HAT0X) return "D PAD X";
        if (code == ABS_HAT0Y) return "D PAD Y";
    }
    return "CONTROL EVENT";
}

static void safe_uppercase(char *destination, size_t capacity, const char *source)
{
    uppercase_line(destination, capacity, source);
    if (!destination[0]) (void)snprintf(destination, capacity, "UNNAMED NETWORK");
}

static void draw_wifi_list(struct framebuffer *fb, const struct wifi_ui *wifi)
{
    unsigned total = wifi->list.count + 3, first, row;
    char connected[GUIDE_WIFI_SSID_MAX + 1], address[32], line[96];
    int online = guide_wifi_status(connected, sizeof(connected), address, sizeof(address));
    draw_header(fb, "WIFI");
    if (!guide_wifi_available()) {
        draw_centered(fb, 155, "WIFI RADIO NOT READY", 3, color(fb, 245, 177, 52));
        draw_centered(fb, 225, "INSTALL OR RESTART THE RADIO", 2, color(fb, 244, 241, 228));
        draw_footer(fb, "CLIENT MODE ONLY", "B BACK"); present(fb); return;
    }
    if (online) {
        char visible[48]; safe_uppercase(visible, sizeof(visible), connected);
        (void)snprintf(line, sizeof(line), "CONNECTED  %s  %s", visible, address);
    } else (void)snprintf(line, sizeof(line), "%s", wifi->list.message);
    draw_centered(fb, 78, line, 2, color(fb, online ? 104 : 245, online ? 207 : 177, online ? 72 : 52));
    first = wifi->list.selected > 4 ? wifi->list.selected - 4 : 0;
    if (first + 5 > total) first = total > 5 ? total - 5 : 0;
    for (row = 0; row < 5 && first + row < total; ++row) {
        unsigned index = first + row, y = 120 + row * 55;
        char label[64];
        if (index < wifi->list.count) {
            char name[40]; safe_uppercase(name, sizeof(name), wifi->list.networks[index].ssid);
            (void)snprintf(label, sizeof(label), "%s  %s  %d DBM", name,
                           wifi->list.networks[index].secured ? "LOCK" : "OPEN",
                           wifi->list.networks[index].signal_dbm);
        } else if (index == wifi->list.count) (void)snprintf(label, sizeof(label), "RESCAN");
        else if (index == wifi->list.count + 1) (void)snprintf(label, sizeof(label), "DISCONNECT");
        else (void)snprintf(label, sizeof(label), "FORGET SAVED NETWORK");
        if (index == wifi->list.selected) {
            fill_rect(fb, 45, y - 10, fb->var.xres - 90, 42, color(fb, 30, 27, 19));
            draw_diamond(fb, 62, y + 7, 6, color(fb, 245, 177, 52));
            draw_text(fb, 82, y, label, 2, color(fb, 245, 177, 52));
        } else draw_text(fb, 82, y, label, 2, color(fb, 244, 241, 228));
        draw_rect(fb, 45, y - 10, fb->var.xres - 90, 42, color(fb, 42, 74, 82));
    }
    draw_scrollbar(fb, 27, 110, 265, total, first, 5);
    draw_footer(fb, "D-PAD ONLY", "A SELECT  B BACK"); present(fb);
}

static unsigned keyboard_row_length(unsigned row)
{
    static const unsigned lengths[] = {10, 9, 10, 10, 6};
    return row < 5 ? lengths[row] : 0;
}

static const char *keyboard_row(unsigned page, unsigned row)
{
    static const char *lower[] = {"qwertyuiop", "asdfghjkl", "zxcvbnm,./", "1234567890"};
    static const char *upper[] = {"QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM,./", "1234567890"};
    static const char *symbols[] = {"!@#$%^&*()", "-_=+[]{};", "'\"\\|`~<>?:", "1234567890"};
    if (row >= 4) return "";
    return page == 1 ? upper[row] : page == 2 ? symbols[row] : lower[row];
}

static unsigned keyboard_move(unsigned cursor, int horizontal, int vertical)
{
    unsigned row = cursor / 10, column = cursor % 10, length;
    if (row >= 5) { row = 0; column = 0; }
    if (vertical) {
        row = (unsigned)(((int)row + vertical + 5) % 5);
        length = keyboard_row_length(row);
        if (column >= length) column = length - 1;
    }
    length = keyboard_row_length(row);
    if (horizontal < 0) column = column == 0 ? length - 1 : column - 1;
    else if (horizontal > 0) column = (column + 1) % length;
    return row * 10 + column;
}

static void keyboard_label(unsigned page, unsigned cursor, const char *submit,
                           char label[8])
{
    unsigned row = cursor / 10, column = cursor % 10;
    if (row < 4) {
        label[0] = keyboard_row(page, row)[column]; label[1] = '\0';
    } else {
        const char *special[] = {"CASE", "MORE", "SPACE", "DEL", submit, "CANCEL"};
        snprintf(label, 8, "%s", special[column]);
    }
}

static void draw_keyboard_keys(struct framebuffer *fb, unsigned page,
                               unsigned cursor, const char *submit)
{
    unsigned row, column;
    for (row = 0; row < 5; ++row) {
        unsigned length = keyboard_row_length(row);
        unsigned width = row == 4 ? 94 : 56;
        unsigned start = (fb->var.xres - length * width) / 2;
        unsigned y = 158 + row * 48;
        for (column = 0; column < length; ++column) {
            unsigned key = row * 10 + column;
            unsigned x = start + column * width;
            char label[8]; keyboard_label(page, key, submit, label);
            if (key == cursor)
                fill_rect(fb, x - 5, y - 7, width - 4, 30, color(fb, 30, 27, 19));
            draw_rect(fb, x - 5, y - 7, width - 4, 30, color(fb, 42, 74, 82));
            draw_text(fb, x + 5, y, label, row == 4 ? 1 : 2,
                      color(fb, key == cursor ? 245 : 244,
                                key == cursor ? 177 : 241,
                                key == cursor ? 52 : 228));
        }
    }
}

static void draw_wifi_keyboard(struct framebuffer *fb, const struct wifi_ui *wifi)
{
    char network[48], masked[GUIDE_WIFI_PASSWORD_MAX + 1], count[32];
    safe_uppercase(network, sizeof(network), wifi->list.networks[wifi->list.selected].ssid);
    memset(masked, '*', wifi->password_length); masked[wifi->password_length] = '\0';
    (void)snprintf(count, sizeof(count), "PASSWORD %u OF 63", (unsigned)wifi->password_length);
    draw_header(fb, "WIFI PASSWORD");
    draw_centered(fb, 74, network, 2, color(fb, 151, 220, 231));
    draw_centered(fb, 103, count, 2, color(fb, 244, 241, 228));
    draw_centered(fb, 132, masked, 2, color(fb, 245, 177, 52));
    draw_keyboard_keys(fb, wifi->page, wifi->cursor, "JOIN");
    draw_footer(fb, "D-PAD  A SELECT  X SPACE", "B CANCEL"); present(fb);
}

static void draw_wifi_result(struct framebuffer *fb, const struct wifi_ui *wifi)
{
    draw_header(fb, "WIFI RESULT");
    draw_centered(fb, 170, wifi->success ? "SUCCESS" : "NOT CONNECTED", 4,
                  color(fb, wifi->success ? 104 : 220, wifi->success ? 207 : 73,
                        wifi->success ? 72 : 73));
    draw_centered(fb, 250, wifi->result, 2, color(fb, 244, 241, 228));
    draw_footer(fb, "PASSWORD NOT LOGGED", "B BACK"); present(fb);
}

static void draw_node_list(struct framebuffer *fb, const struct node_ui *node)
{
    unsigned total = node->count + 1, first, row;
    draw_header(fb, "NODES");
    if (!guide_wifi_link_up()) {
        draw_centered(fb, 155, "CONNECT WI-FI FIRST", 4, color(fb, 245, 177, 52));
        draw_centered(fb, 235, "NODES USE THE LOCAL NETWORK", 2,
                      color(fb, 244, 241, 228));
        draw_footer(fb, "LOCAL DISCOVERY", "B BACK"); present(fb); return;
    }
    if (node->message[0])
        draw_centered(fb, 72, node->message, 2, color(fb, 245, 177, 52));
    else
        draw_centered(fb, 72, node->count ? "FOUND ON THIS NETWORK" : "NO NODES FOUND",
                      2, color(fb, node->count ? 104 : 245,
                               node->count ? 207 : 177, node->count ? 72 : 52));
    first = node->selected > 4 ? node->selected - 4 : 0;
    if (first + 5 > total) first = total > 5 ? total - 5 : 0;
    for (row = 0; row < 5 && first + row < total; ++row) {
        unsigned index = first + row, y = 120 + row * 55;
        char label[48];
        if (index < node->count) {
            char name[34];
            safe_uppercase(name, sizeof(name), node->candidates[index].name);
            snprintf(label, sizeof(label), "%s%s", name,
                     node->candidates[index].trusted ? "  TRUSTED" : "");
        }
        else snprintf(label, sizeof(label), "SEARCH AGAIN");
        if (index == node->selected) {
            fill_rect(fb, 45, y - 10, fb->var.xres - 90, 42, color(fb, 30, 27, 19));
            draw_diamond(fb, 62, y + 7, 6, color(fb, 245, 177, 52));
            draw_text(fb, 82, y, label, 2, color(fb, 245, 177, 52));
        } else draw_text(fb, 82, y, label, 2, color(fb, 244, 241, 228));
        draw_rect(fb, 45, y - 10, fb->var.xres - 90, 42, color(fb, 42, 74, 82));
    }
    draw_scrollbar(fb, 27, 110, 265, total, first, 5);
    draw_footer(fb, "A PAIR OR SEARCH", "B BACK"); present(fb);
}

static const char *node_key_label(unsigned key)
{
    static const char *labels[] = {"1", "2", "3", "4", "5", "6",
                                    "7", "8", "9", "DEL", "0", "PAIR"};
    return key < 12 ? labels[key] : "";
}

static void draw_node_pair(struct framebuffer *fb, const struct node_ui *node)
{
    unsigned key;
    char name[42], shown[16] = "------";
    safe_uppercase(name, sizeof(name), node->candidates[node->selected].name);
    memcpy(shown, node->code, node->code_length);
    draw_header(fb, "NODE PAIRING");
    draw_centered(fb, 70, name, 2, color(fb, 151, 220, 231));
    draw_centered(fb, 104, shown, 4, color(fb, 245, 177, 52));
    for (key = 0; key < 12; ++key) {
        unsigned row = key / 3, column = key % 3;
        unsigned x = 196 + column * 85, y = 174 + row * 54;
        const char *label = node_key_label(key);
        if (key == node->keypad)
            fill_rect(fb, x - 12, y - 9, 72, 35, color(fb, 30, 27, 19));
        draw_rect(fb, x - 12, y - 9, 72, 35, color(fb, 42, 74, 82));
        draw_text(fb, x, y, label, strlen(label) > 2 ? 1 : 2,
                  color(fb, key == node->keypad ? 245 : 244,
                            key == node->keypad ? 177 : 241,
                            key == node->keypad ? 52 : 228));
    }
    if (node->message[0])
        draw_centered(fb, 400, node->message, 2, color(fb, 220, 73, 73));
    draw_footer(fb, "ENTER CODE SHOWN ON NODE", "B CANCEL"); present(fb);
}

static void draw_node_result(struct framebuffer *fb, const struct node_ui *node)
{
    char name[42], android[48];
    safe_uppercase(name, sizeof(name), node->paired_name);
    safe_uppercase(android, sizeof(android), node->android_state);
    draw_header(fb, "NODE LINK");
    draw_centered(fb, 132, node->success ? "PAIRED" : "NOT PAIRED", 5,
                  color(fb, node->success ? 104 : 220,
                            node->success ? 207 : 73, node->success ? 72 : 73));
    draw_centered(fb, 218, node->success ? name : node->message, 3,
                  color(fb, 244, 241, 228));
    if (node->success) {
        snprintf(android, sizeof(android), "ANDROID %s", node->android_state);
        safe_uppercase(name, sizeof(name), android);
        draw_centered(fb, 290, name, 2, color(fb, 151, 220, 231));
        draw_centered(fb, 338, node->message[0] ? node->message :
                      "SESSION ENDS WHEN EITHER DEVICE STOPS", 2,
                      color(fb, node->message[0] ? 220 : 244,
                                node->message[0] ? 73 : 241,
                                node->message[0] ? 73 : 228));
    }
    draw_footer_three(fb, node->success ? "A MEDIA" : "LOCAL LINK",
                      node->success && !node->trusted ? "X TRUST" :
                      node->trusted ? "TRUSTED" : "", "B NODES"); present(fb);
}

static void draw_media_list(struct framebuffer *fb, const struct node_ui *node)
{
    unsigned first, row;
    char summary[64];
    draw_header(fb, "NODE MEDIA");
    if (node->message[0])
        draw_centered(fb, 68, node->message, 2, color(fb, 245, 177, 52));
    else {
        snprintf(summary, sizeof(summary), "%u OF %u FILES AVAILABLE",
                 node->media_count, node->media_total);
        draw_centered(fb, 68, summary, 2, color(fb, 151, 220, 231));
    }
    if (!node->media_count) {
        draw_centered(fb, 170, "NO SHARED MEDIA", 4, color(fb, 245, 177, 52));
        draw_centered(fb, 248, "CHOOSE A MEDIA FOLDER ON THE NODE", 2,
                      color(fb, 244, 241, 228));
        draw_footer(fb, "A REFRESH", "B HOME"); present(fb); return;
    }
    first = node->media_selected > 5 ? node->media_selected - 5 : 0;
    if (first + 6 > node->media_count)
        first = node->media_count > 6 ? node->media_count - 6 : 0;
    for (row = 0; row < 6 && first + row < node->media_count; ++row) {
        unsigned index = first + row, y = 93 + row * 49;
        char name[39], label[48];
        safe_uppercase(name, sizeof(name), node->media[index].name);
        snprintf(label, sizeof(label), "%s  %s", node->media[index].kind, name);
        safe_uppercase(label, sizeof(label), label);
        if (index == node->media_selected) {
            fill_rect(fb, 38, y - 9, fb->var.xres - 76, 38, color(fb, 30, 27, 19));
            draw_diamond(fb, 55, y + 7, 6, color(fb, 245, 177, 52));
            draw_text(fb, 75, y, label, 2, color(fb, 245, 177, 52));
        } else draw_text(fb, 75, y, label, 2, color(fb, 244, 241, 228));
        draw_rect(fb, 38, y - 9, fb->var.xres - 76, 38, color(fb, 42, 74, 82));
    }
    draw_scrollbar(fb, 22, 84, 285, node->media_count, first, 6);
    draw_footer(fb, "A PLAY", "B HOME"); present(fb);
}

static void draw_media_starting(struct framebuffer *fb, const struct node_ui *node)
{
    char name[49];
    safe_uppercase(name, sizeof(name), node->media[node->media_selected].name);
    draw_header(fb, "NODE MEDIA");
    draw_centered(fb, 142, "STARTING PLAYBACK", 4, color(fb, 245, 177, 52));
    draw_centered(fb, 224, name, 2, color(fb, 244, 241, 228));
    draw_centered(fb, 292, "STREAMING FROM YOUR NODE", 2, color(fb, 151, 220, 231));
    draw_footer_three(fb, "B PAUSE", "L2 R2 SEEK", "A STOP"); present(fb);
}

static void draw_media_subtitles(struct framebuffer *fb, const struct node_ui *node)
{
    const struct media_item *item = &node->media[node->media_selected];
    unsigned row;
    draw_header(fb, "SUBTITLES");
    draw_centered(fb, 65, "SELECT A TRACK", 2, color(fb, 151, 220, 231));
    for (row = 0; row <= item->subtitle_count && row < GUIDE_SUBTITLE_MAX + 1; ++row) {
        unsigned y = 106 + row * 36;
        const char *label = row == 0 ? "OFF" : item->subtitles[row - 1];
        if (row == node->subtitle_menu_selected) {
            fill_rect(fb, 80, y - 7, fb->var.xres - 160, 29, color(fb, 30, 27, 19));
            draw_diamond(fb, 99, y + 6, 5, color(fb, 245, 177, 52));
            draw_text(fb, 118, y, label, 2, color(fb, 245, 177, 52));
        } else draw_text(fb, 118, y, label, 2, color(fb, 244, 241, 228));
    }
    draw_footer(fb, "A USE TRACK", "B CANCEL"); present(fb);
}

static void draw_wikipedia_home(struct framebuffer *fb, const struct wikipedia_ui *wiki)
{
    draw_header(fb, "WIKIPEDIA");
    if (!guide_wikipedia_installed()) {
        draw_centered(fb, 132, "NOT INSTALLED", 4, color(fb, 245, 177, 52));
        draw_centered(fb, 224, "INSTALL VERSION 0.3 FROM CARTRIDGE", 2,
                      color(fb, 244, 241, 228));
        draw_centered(fb, 286, "PLAIN TEXT  VERIFIED HTTPS", 2,
                      color(fb, 151, 220, 231));
        draw_footer(fb, "BROWSER UNAVAILABLE", "B BACK");
    } else {
        draw_centered(fb, 108, "WIKIPEDIA", 5, color(fb, 244, 241, 228));
        draw_centered(fb, 196, guide_wifi_link_up() ? "READY TO SEARCH" : "OFFLINE",
                      3, color(fb, guide_wifi_link_up() ? 104 : 245,
                               guide_wifi_link_up() ? 207 : 177,
                               guide_wifi_link_up() ? 72 : 52));
        draw_centered(fb, 258, wiki->message[0] ? wiki->message :
                      "PLAIN ARTICLES  NO WEB SCRIPTS", 2, color(fb, 151, 220, 231));
        draw_centered(fb, 320, "SEARCH TEXT IS SENT TO WIKIPEDIA", 2,
                      color(fb, 244, 241, 228));
        draw_footer(fb, "A SEARCH", "B BACK");
    }
    present(fb);
}

static void draw_wikipedia_keyboard(struct framebuffer *fb, const struct wikipedia_ui *wiki)
{
    char count[32], shown[GUIDE_WIKI_QUERY_MAX + 1];
    snprintf(count, sizeof(count), "SEARCH %u OF %u", (unsigned)wiki->query_length,
             GUIDE_WIKI_QUERY_MAX);
    safe_uppercase(shown, sizeof(shown), wiki->query);
    draw_header(fb, "WIKIPEDIA SEARCH");
    draw_centered(fb, 78, count, 2, color(fb, 151, 220, 231));
    draw_centered(fb, 110, shown, 2, color(fb, 245, 177, 52));
    draw_keyboard_keys(fb, wiki->keyboard_page, wiki->cursor, "SEARCH");
    draw_footer(fb, "D-PAD  A SELECT  X SPACE", "B CANCEL"); present(fb);
}

static void draw_wikipedia_results(struct framebuffer *fb, const struct wikipedia_ui *wiki)
{
    unsigned first, row;
    draw_header(fb, "WIKIPEDIA RESULTS");
    if (wiki->message[0])
        draw_centered(fb, 58, wiki->message, 1, color(fb, 220, 73, 73));
    if (!wiki->result_count) {
        draw_centered(fb, 180, "NO ARTICLES FOUND", 4, color(fb, 245, 177, 52));
        draw_footer(fb, "TRY ANOTHER SEARCH", "B BACK"); present(fb); return;
    }
    first = wiki->selected_result > 5 ? wiki->selected_result - 5 : 0;
    if (first + 6 > wiki->result_count)
        first = wiki->result_count > 6 ? wiki->result_count - 6 : 0;
    for (row = 0; row < 6 && first + row < wiki->result_count; ++row) {
        unsigned index = first + row, y = 88 + row * 52;
        char title[31], detail[48];
        safe_uppercase(title, sizeof(title), wiki->results[index].title);
        snprintf(detail, sizeof(detail), "%s  %uW", title,
                 wiki->results[index].word_count);
        if (index == wiki->selected_result) {
            fill_rect(fb, 38, y - 10, fb->var.xres - 76, 40, color(fb, 30, 27, 19));
            draw_diamond(fb, 55, y + 7, 6, color(fb, 245, 177, 52));
            draw_text(fb, 75, y, detail, 2, color(fb, 245, 177, 52));
        } else draw_text(fb, 75, y, detail, 2, color(fb, 244, 241, 228));
        draw_rect(fb, 38, y - 10, fb->var.xres - 76, 40, color(fb, 42, 74, 82));
    }
    draw_scrollbar(fb, 22, 78, 300, wiki->result_count, first, 6);
    draw_footer(fb, "A OPEN ARTICLE", "B SEARCH"); present(fb);
}

static size_t wikipedia_draw_lines(struct framebuffer *fb, const char *text,
                                   size_t length, size_t offset)
{
    unsigned line;
    size_t position = offset;
    for (line = 0; line < 14 && position < length; ++line) {
        char visible[49];
        size_t start, end, next, count, candidate;
        while (position < length &&
               (text[position] == '\r' || text[position] == ' ' || text[position] == '\t'))
            ++position;
        if (position >= length) break;
        if (text[position] == '\n') { ++position; continue; }
        start = position;
        end = start + 48 < length ? start + 48 : length;
        for (candidate = start; candidate < end; ++candidate)
            if (text[candidate] == '\n') { end = candidate; break; }
        next = end;
        if (end < length && text[end] != '\n' && text[end] != ' ') {
            candidate = end;
            while (candidate > start && text[candidate] != ' ' && text[candidate] != '\n') --candidate;
            if (candidate > start) next = candidate;
        }
        count = next - start;
        if (count > 48) count = 48;
        memcpy(visible, text + start, count); visible[count] = '\0';
        draw_text(fb, 30, 90 + line * 23, visible, 2, color(fb, 244, 241, 228));
        position = next;
        while (position < length &&
               (text[position] == '\r' || text[position] == ' ' || text[position] == '\t'))
            ++position;
        if (position < length && text[position] == '\n') ++position;
    }
    return position;
}

static void draw_wikipedia_article(struct framebuffer *fb, struct wikipedia_ui *wiki)
{
    char title[49], position[40], links[40];
    size_t next;
    safe_uppercase(title, sizeof(title), wiki->title);
    draw_header(fb, "WIKIPEDIA ARTICLE");
    draw_centered(fb, 66, title, 2, color(fb, 151, 220, 231));
    next = wikipedia_draw_lines(fb, wiki->text ? wiki->text : "", wiki->text_length,
                                wiki->page_offsets[wiki->page]);
    wiki->visible_end = next;
    if (next < wiki->text_length && wiki->page + 1 < GUIDE_WIKI_PAGE_MAX) {
        wiki->page_offsets[wiki->page + 1] = next;
        if (wiki->known_pages < wiki->page + 2) wiki->known_pages = wiki->page + 2;
    }
    snprintf(position, sizeof(position), "B BACK  PAGE %u%s", wiki->page + 1,
             next < wiki->text_length ? "  MORE" : "  END");
    snprintf(links, sizeof(links), wiki->link_count ? "A LINKS %u" : "NO LINKS",
             wiki->link_count);
    draw_footer(fb, links, position); present(fb);
}

static void draw_wikipedia_links(struct framebuffer *fb, const struct wikipedia_ui *wiki)
{
    unsigned first, row;
    char heading[64];
    draw_header(fb, "ARTICLE LINKS");
    snprintf(heading, sizeof(heading), "%u LINKS IN %.36s", wiki->link_count, wiki->title);
    draw_centered(fb, 58, heading, 1, color(fb, 151, 220, 231));
    if (!wiki->link_count) {
        draw_centered(fb, 190, "NO ARTICLE LINKS", 4, color(fb, 245, 177, 52));
        draw_footer(fb, "", "B ARTICLE"); present(fb); return;
    }
    first = wiki->selected_link > 6 ? wiki->selected_link - 6 : 0;
    if (first + 7 > wiki->link_count)
        first = wiki->link_count > 7 ? wiki->link_count - 7 : 0;
    for (row = 0; row < 7 && first + row < wiki->link_count; ++row) {
        unsigned index = first + row, y = 86 + row * 45;
        char title[35], label[48];
        safe_uppercase(title, sizeof(title), wiki->links[index].title);
        snprintf(label, sizeof(label), "%u %s", index + 1, title);
        if (index == wiki->selected_link) {
            fill_rect(fb, 38, y - 8, fb->var.xres - 76, 35, color(fb, 30, 27, 19));
            draw_diamond(fb, 55, y + 7, 6, color(fb, 245, 177, 52));
            draw_text(fb, 75, y, label, 2, color(fb, 245, 177, 52));
        } else draw_text(fb, 75, y, label, 2, color(fb, 244, 241, 228));
    }
    draw_scrollbar(fb, 22, 76, 305, wiki->link_count, first, 7);
    draw_footer(fb, "A OPEN LINK", "B ARTICLE"); present(fb);
}

static unsigned wikipedia_first_link_on_page(const struct wikipedia_ui *wiki)
{
    size_t position = wiki->page_offsets[wiki->page];
    while (position < wiki->visible_end && position < wiki->text_length) {
        if (wiki->text[position] == '[' && position + 2 < wiki->visible_end) {
            char *end = NULL;
            unsigned long number = strtoul(wiki->text + position + 1, &end, 10);
            if (end && end > wiki->text + position + 1 && *end == ']' &&
                number > 0 && number <= wiki->link_count)
                return (unsigned)number - 1;
        }
        ++position;
    }
    return 0;
}

static void draw_input_test(struct framebuffer *fb, unsigned type, unsigned code, int value)
{
    char detail[64];
    draw_header(fb, "INPUT");
    draw_centered(fb, 116, "INPUT TEST", 5, color(fb, 244, 241, 228));
    draw_centered(fb, 194, input_name(type, code), 3, color(fb, 245, 177, 52));
    snprintf(detail, sizeof(detail), "TYPE %u  CODE %u  VALUE %d", type, code, value);
    draw_centered(fb, 284, detail, 2, color(fb, 151, 220, 231));
    draw_footer(fb, "LIVE INPUT", "B BACK"); present(fb);
}

static void draw_system_info(struct framebuffer *fb, unsigned input_count)
{
    struct utsname name;
    char line[80];
    draw_header(fb, "SYSTEM");
    draw_centered(fb, 96, "SYSTEM INFO", 4, color(fb, 244, 241, 228));
    snprintf(line, sizeof(line), "DISPLAY %u X %u", fb->var.xres, fb->var.yres);
    draw_text(fb, 86, 178, line, 3, color(fb, 151, 220, 231));
    snprintf(line, sizeof(line), "INPUT DEVICES %u", input_count);
    draw_text(fb, 86, 236, line, 3, color(fb, 151, 220, 231));
    if (uname(&name) == 0) snprintf(line, sizeof(line), "KERNEL %.32s", name.release);
    else snprintf(line, sizeof(line), "KERNEL UNKNOWN");
    draw_text(fb, 86, 294, line, 3, color(fb, 151, 220, 231));
    snprintf(line, sizeof(line), "WIFI INTERFACE %s",
             access("/sys/class/net/wlan0", F_OK) == 0 ? "READY" : "NOT YET");
    draw_text(fb, 86, 342, line, 2, color(fb, 245, 177, 52));
    draw_footer(fb, "TEST 03", "B BACK"); present(fb);
}

static void log_text_file(FILE *log, const char *label, const char *path)
{
    char content[512];
    ssize_t count;
    int fd = open(path, O_RDONLY | O_NOFOLLOW);
    if (fd < 0) {
        fprintf(log, "%s unavailable path=%s error=%s\n", label, path, strerror(errno));
        return;
    }
    count = read(fd, content, sizeof(content) - 1);
    close(fd);
    if (count < 0) {
        fprintf(log, "%s unreadable path=%s error=%s\n", label, path, strerror(errno));
        return;
    }
    content[count] = '\0';
    fprintf(log, "%s path=%s value=", label, path);
    fwrite(content, 1, (size_t)count, log);
    if (count == 0 || content[count - 1] != '\n') fputc('\n', log);
}

static void log_directory(FILE *log, const char *label, const char *path)
{
    DIR *directory = opendir(path);
    struct dirent *entry;
    if (!directory) {
        fprintf(log, "%s unavailable path=%s error=%s\n", label, path, strerror(errno));
        return;
    }
    fprintf(log, "%s path=%s entries=", label, path);
    while ((entry = readdir(directory)) != NULL)
        if (strcmp(entry->d_name, ".") != 0 && strcmp(entry->d_name, "..") != 0)
            fprintf(log, "%s ", entry->d_name);
    fputc('\n', log);
    closedir(directory);
}

static void log_wifi_diagnostics(FILE *log)
{
    DIR *directory;
    struct dirent *entry;
    char path[256];
    struct utsname name;
    fprintf(log, "WIFI HARDWARE DIAGNOSTICS BEGIN\n");
    if (uname(&name) == 0)
        fprintf(log, "kernel release=%s machine=%s\n", name.release, name.machine);
    log_directory(log, "network interfaces", "/sys/class/net");
    log_directory(log, "sdio devices", "/sys/bus/sdio/devices");
    log_text_file(log, "loaded modules", "/proc/modules");
    directory = opendir("/sys/bus/sdio/devices");
    if (directory) {
        while ((entry = readdir(directory)) != NULL) {
            if (entry->d_name[0] == '.') continue;
            if (snprintf(path, sizeof(path), "/sys/bus/sdio/devices/%s/modalias", entry->d_name) < (int)sizeof(path))
                log_text_file(log, "sdio modalias", path);
            if (snprintf(path, sizeof(path), "/sys/bus/sdio/devices/%s/uevent", entry->d_name) < (int)sizeof(path))
                log_text_file(log, "sdio uevent", path);
        }
        closedir(directory);
    }
    fprintf(log, "WIFI HARDWARE DIAGNOSTICS END\n");
    fflush(log);
}

static void draw_cartridge_list(struct framebuffer *fb,
                                const struct guide_cartridge_catalog *catalog)
{
    const char *state = "NO EXT STORAGE";
    const char *guidance = "INSERT STORAGE IN TF2";
    uint32_t state_color = color(fb, 245, 177, 52);
    char position[32], version[48];
    if (catalog->state == GUIDE_CARTRIDGE_MOUNT_ERROR) {
        state = "EXT STORAGE DETECTED";
        guidance = "STORAGE COULD NOT BE READ";
    } else if (catalog->state == GUIDE_CARTRIDGE_EMPTY) {
        state = "EXT STORAGE LOADED";
        guidance = "NO GUIDE CARTRIDGES ON STORAGE";
    } else if (catalog->state == GUIDE_CARTRIDGE_INVALID) {
        state = "EXT STORAGE LOADED";
        guidance = "PACKAGE FORMAT NOT RECOGNIZED";
    }
    else if (catalog->state == GUIDE_CARTRIDGE_READY) {
        state = "CARTRIDGE BROWSER";
        state_color = color(fb, 104, 207, 72);
    }
    draw_header(fb, "CARTRIDGES");
    draw_centered(fb, 86, state, 3, state_color);
    if (catalog->state == GUIDE_CARTRIDGE_READY) {
        const struct guide_cartridge *item = &catalog->items[catalog->selected];
        snprintf(position, sizeof(position), "%u OF %u", catalog->selected + 1, catalog->count);
        snprintf(version, sizeof(version), "%s  VERSION %s", item->kind, item->version);
        draw_centered(fb, 132, position, 2, color(fb, 151, 220, 231));
        fill_rect(fb, 46, 168, fb->var.xres - 92, 154, color(fb, 30, 27, 19));
        draw_rect(fb, 46, 168, fb->var.xres - 92, 154, color(fb, 42, 74, 82));
        draw_centered(fb, 192, item->name, 4, color(fb, 245, 177, 52));
        draw_centered(fb, 252, version, 2, color(fb, 151, 220, 231));
        draw_centered(fb, 292, item->summary, 2, color(fb, 244, 241, 228));
        draw_centered(fb, 350, "UNSIGNED PACKAGE", 2, color(fb, 245, 177, 52));
        draw_footer(fb, "D-PAD OR STICK", "A OPEN  B BACK");
    } else {
        draw_centered(fb, 210, catalog->detail, 2, color(fb, 151, 220, 231));
        draw_centered(fb, 276, guidance, 2,
                      color(fb, 244, 241, 228));
        draw_footer(fb, "READ ONLY", "A SCAN  B BACK");
    }
    present(fb);
}

static void draw_cartridge_detail(struct framebuffer *fb,
                                  const struct guide_cartridge_catalog *catalog)
{
    const struct guide_cartridge *item = &catalog->items[catalog->selected];
    char identity[96], action[96], capability[64];
    const char *verification = "NOT CHECKED";
    uint32_t verification_color = color(fb, 245, 177, 52);
    snprintf(identity, sizeof(identity), "%s  %s", item->id, item->version);
    uppercase_line(identity, sizeof(identity), identity);
    if (item->capability_count)
        snprintf(capability, sizeof(capability), "REQUESTS %s", item->capability);
    else snprintf(capability, sizeof(capability), "REQUESTS NO CAPABILITIES");
    if (item->action[0]) {
        snprintf(action, sizeof(action), "ACTION %s", item->action);
        uppercase_line(action, sizeof(action), action);
    } else snprintf(action, sizeof(action), "CONTENT ONLY");
    if (item->verification == GUIDE_CARTRIDGE_VERIFIED) {
        verification = "FILES VERIFIED";
        verification_color = color(fb, 104, 207, 72);
    } else if (item->verification == GUIDE_CARTRIDGE_VERIFY_FAILED) {
        verification = "VERIFICATION FAILED";
        verification_color = color(fb, 220, 73, 73);
    } else if (item->verification == GUIDE_CARTRIDGE_VERIFY_UNAVAILABLE) {
        verification = "VERIFY TOOL MISSING";
        verification_color = color(fb, 220, 73, 73);
    }
    draw_header(fb, "CARTRIDGE");
    draw_centered(fb, 86, item->name, 4, color(fb, 244, 241, 228));
    draw_centered(fb, 142, identity, 2, color(fb, 151, 220, 231));
    draw_centered(fb, 202, verification, 3, verification_color);
    draw_centered(fb, 258, "UNSIGNED", 2, color(fb, 245, 177, 52));
    draw_centered(fb, 304, capability, 2, color(fb, 244, 241, 228));
    draw_centered(fb, 344, action, 2, color(fb, 151, 220, 231));
    if (guide_wifi_install_supported(item) || guide_developer_link_install_supported(item) ||
        guide_wikipedia_install_supported(item))
        draw_footer(fb, "A INSTALL", "B BACK");
    else draw_footer(fb, "VIEW ONLY", "B BACK");
    present(fb);
}

static void draw_install_confirm(struct framebuffer *fb, const struct guide_cartridge *item)
{
    int developer = guide_developer_link_install_supported(item);
    int wikipedia = guide_wikipedia_install_supported(item);
    draw_header(fb, "INSTALL");
    draw_centered(fb, 100, developer ? "INSTALL DEVELOPER LINK" :
                  wikipedia ? "INSTALL WIKIPEDIA" : "INSTALL WIFI", 4,
                  color(fb, 244, 241, 228));
    draw_centered(fb, 178, "MODIFIES THIS DECK", 3, color(fb, 245, 177, 52));
    draw_centered(fb, 240, "ONLY FOR RG35XX H  KERNEL 4.9.170", 2,
                  color(fb, 151, 220, 231));
    draw_centered(fb, 286, developer ? "KEY ONLY  OFF BY DEFAULT" :
                  wikipedia ? "PLAIN TEXT  VERIFIED HTTPS" : "NO NETWORK PASSWORDS INCLUDED", 2,
                  color(fb, 244, 241, 228));
    draw_centered(fb, 342, "FAILED CHANGES WILL BE UNDONE", 2,
                  color(fb, 104, 207, 72));
    draw_footer(fb, "A CONFIRM", "B CANCEL");
    present(fb);
}

static int developer_link_control(const char *command, FILE *log)
{
    pid_t child;
    int status;
    if (!guide_developer_link_installed()) return -1;
    child = fork();
    if (child == 0) {
        execl("/usr/sbin/guide-devlink-control", "guide-devlink-control", command,
              (char *)NULL);
        _exit(127);
    }
    if (child < 0 || waitpid(child, &status, 0) < 0 || !WIFEXITED(status)) return -1;
    fprintf(log, "developer_link command=%s status=%d\n", command, WEXITSTATUS(status));
    fflush(log);
    return WEXITSTATUS(status) == 0 ? 0 : -1;
}

static int developer_link_active(FILE *log)
{
    return developer_link_control("status", log) == 0;
}

static void draw_developer_link(struct framebuffer *fb, FILE *log, const char *message)
{
    int installed = guide_developer_link_installed();
    int active = installed && developer_link_active(log);
    char connected[GUIDE_WIFI_SSID_MAX + 1] = "", address[48] = "";
    char endpoint[80] = "";
    draw_header(fb, "DEVELOPER LINK");
    if (!installed) {
        draw_centered(fb, 135, "NOT INSTALLED", 4, color(fb, 245, 177, 52));
        draw_centered(fb, 230, "INSTALL FROM A GUIDE CARTRIDGE", 2,
                      color(fb, 244, 241, 228));
        draw_footer(fb, "LINK UNAVAILABLE", "B BACK");
    } else if (active) {
        (void)guide_wifi_status(connected, sizeof(connected), address, sizeof(address));
        snprintf(endpoint, sizeof(endpoint), "%s:2222", address[0] ? address : "LOCAL WIFI");
        draw_centered(fb, 115, "REMOTE ACCESS ACTIVE", 4, color(fb, 220, 73, 73));
        draw_centered(fb, 205, endpoint, 3, color(fb, 151, 220, 231));
        draw_centered(fb, 270, "KEY ONLY  LOCAL WIFI", 2, color(fb, 244, 241, 228));
        draw_centered(fb, 325, message && message[0] ? message : "PHYSICALLY ENABLED", 2,
                      color(fb, 245, 177, 52));
        draw_footer(fb, "A TURN OFF", "B BACK");
    } else {
        draw_centered(fb, 135, "DEVELOPER LINK OFF", 4, color(fb, 104, 207, 72));
        draw_centered(fb, 225, message && message[0] ? message : "NO REMOTE ACCESS", 2,
                      color(fb, 244, 241, 228));
        draw_centered(fb, 290, "REQUIRES CONNECTED WIFI", 2, color(fb, 151, 220, 231));
        draw_footer(fb, "A TURN ON", "B BACK");
    }
    present(fb);
}

static void draw_install_result(struct framebuffer *fb, const char *message, int success)
{
    draw_header(fb, "INSTALL");
    draw_centered(fb, 130, success ? "INSTALL COMPLETE" : "INSTALL STOPPED", 4,
                  color(fb, success ? 104 : 220, success ? 207 : 73, success ? 72 : 73));
    draw_centered(fb, 238, message, 3, color(fb, 244, 241, 228));
    draw_centered(fb, 310, success ? "CARTRIDGE MAY BE REMOVED AFTER EXIT" :
                  "NO PARTIAL INSTALL WAS KEPT", 2, color(fb, 151, 220, 231));
    draw_footer(fb, "RESULT RECORDED", "B BACK");
    present(fb);
}

static void draw_shutdown_confirm(struct framebuffer *fb)
{
    draw_header(fb, "POWER");
    draw_centered(fb, 132, "SHUT DOWN SAFELY", 4,
                  color(fb, 244, 241, 228));
    draw_centered(fb, 220, "SAVE DATA AND POWER OFF", 2,
                  color(fb, 151, 220, 231));
    draw_centered(fb, 298, "A YES", 3, color(fb, 245, 177, 52));
    draw_centered(fb, 350, "B CANCEL", 3, color(fb, 244, 241, 228));
    present(fb);
}

static void safe_shutdown(struct framebuffer *fb, FILE *log,
                          struct guide_cartridge_catalog *catalog)
{
    int remounted, remount_error = 0, reboot_error;
    char wifi_message[80];
    draw_header(fb, "POWER");
    draw_centered(fb, 176, "SHUTTING DOWN", 5,
                  color(fb, 244, 241, 228));
    draw_centered(fb, 270, "SAVING DATA", 3,
                  color(fb, 245, 177, 52));
    draw_centered(fb, 330, "PLEASE WAIT", 2,
                  color(fb, 151, 220, 231));
    present(fb);

    fprintf(log, "safe_shutdown requested\n");
    record_clock_floor(log);
    if (guide_developer_link_installed()) (void)developer_link_control("stop", log);
    (void)guide_wifi_disconnect(log, wifi_message, sizeof(wifi_message));
    guide_cartridge_release(catalog, log);
    sync();
    remounted = mount(NULL, "/", NULL, MS_REMOUNT | MS_RDONLY, NULL);
    if (remounted != 0) {
        remount_error = errno;
        fprintf(log, "root read-only remount unavailable error=%s; continuing with synced kernel power-off\n",
                strerror(remount_error));
    }
    fflush(log);
    if (log != stderr) {
        (void)fsync(fileno(log));
        fclose(log);
    }
    sync();
    (void)reboot(RB_POWER_OFF);
    reboot_error = errno;

    draw_header(fb, "POWER");
    if (remounted == 0) {
        draw_centered(fb, 190, "SAFE TO POWER OFF", 4,
                      color(fb, 104, 207, 72));
        draw_centered(fb, 270, "KERNEL POWER-OFF DID NOT COMPLETE", 2,
                      color(fb, 151, 220, 231));
    } else {
        draw_centered(fb, 190, "SHUTDOWN ERROR", 4,
                      color(fb, 220, 73, 73));
        draw_centered(fb, 250, "KERNEL POWER-OFF FAILED", 2,
                      color(fb, 244, 241, 228));
        draw_centered(fb, 290, "FILESYSTEM MAY REMAIN ACTIVE", 2,
                      color(fb, 244, 241, 228));
        draw_centered(fb, 330, "DO NOT REMOVE THE CARD", 2,
                      color(fb, 245, 177, 52));
    }
    (void)remount_error;
    (void)reboot_error;
    present(fb);
    for (;;) sleep(3600);
}

static void redraw_screen(struct framebuffer *fb, enum screen screen,
                          unsigned selected, unsigned input_count,
                          const struct guide_cartridge_catalog *catalog,
                          const char *install_message, int install_success,
                          const struct wifi_ui *wifi, struct node_ui *node,
                          struct wikipedia_ui *wiki)
{
    if (screen == SCREEN_MENU) draw_menu(fb, selected);
    else if (screen == SCREEN_WIFI_LIST) draw_wifi_list(fb, wifi);
    else if (screen == SCREEN_WIFI_KEYBOARD) draw_wifi_keyboard(fb, wifi);
    else if (screen == SCREEN_WIFI_RESULT) draw_wifi_result(fb, wifi);
    else if (screen == SCREEN_NODE_LIST) draw_node_list(fb, node);
    else if (screen == SCREEN_NODE_PAIR) draw_node_pair(fb, node);
    else if (screen == SCREEN_NODE_RESULT) draw_node_result(fb, node);
    else if (screen == SCREEN_MEDIA_LIST) draw_media_list(fb, node);
    else if (screen == SCREEN_MEDIA_PLAYING) draw_media_starting(fb, node);
    else if (screen == SCREEN_MEDIA_SUBTITLES) draw_media_subtitles(fb, node);
    else if (screen == SCREEN_CARTRIDGE_LIST) draw_cartridge_list(fb, catalog);
    else if (screen == SCREEN_CARTRIDGE_DETAIL) draw_cartridge_detail(fb, catalog);
    else if (screen == SCREEN_INSTALL_CONFIRM && catalog->state == GUIDE_CARTRIDGE_READY)
        draw_install_confirm(fb, &catalog->items[catalog->selected]);
    else if (screen == SCREEN_INSTALL_RESULT)
        draw_install_result(fb, install_message, install_success);
    else if (screen == SCREEN_DEVELOPER_LINK) draw_developer_link(fb, stderr, "");
    else if (screen == SCREEN_WIKIPEDIA_HOME) draw_wikipedia_home(fb, wiki);
    else if (screen == SCREEN_WIKIPEDIA_KEYBOARD) draw_wikipedia_keyboard(fb, wiki);
    else if (screen == SCREEN_WIKIPEDIA_RESULTS) draw_wikipedia_results(fb, wiki);
    else if (screen == SCREEN_WIKIPEDIA_ARTICLE) draw_wikipedia_article(fb, wiki);
    else if (screen == SCREEN_WIKIPEDIA_LINKS) draw_wikipedia_links(fb, wiki);
    else if (screen == SCREEN_DISPLAY) draw_display_test(fb);
    else if (screen == SCREEN_INPUT) draw_input_test(fb, 0, 0, 0);
    else if (screen == SCREEN_SYSTEM) draw_system_info(fb, input_count);
}

static void close_inputs(struct input_set *inputs)
{
    int i;
    for (i = 0; i < inputs->count; ++i) close(inputs->pollfds[i].fd);
    inputs->count = 0;
}

static void open_inputs(struct input_set *inputs, FILE *log)
{
    int index;
    close_inputs(inputs);
    memset(inputs->axes, 0, sizeof(inputs->axes));
    for (index = 0; index < MAX_INPUTS; ++index) {
        char path[64], name[128] = "unknown";
        int fd, code;
        snprintf(path, sizeof(path), "/dev/input/event%d", index);
        fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd < 0) continue;
        inputs->pollfds[inputs->count].fd = fd;
        inputs->pollfds[inputs->count].events = POLLIN;
        inputs->pollfds[inputs->count].revents = 0;
        (void)ioctl(fd, EVIOCGNAME(sizeof(name)), name);
        fprintf(log, "input=%s name=%s\n", path, name);
        for (code = 0; code < ABS_CNT; ++code) {
            struct input_absinfo information;
            struct axis_profile *profile;
            if (!(code == ABS_X || code == ABS_Y || code == ABS_Z ||
                  code == ABS_RX || code == ABS_RY || code == ABS_RZ)) continue;
            if (ioctl(fd, EVIOCGABS(code), &information) != 0) continue;
            profile = &inputs->axes[inputs->count][code];
            profile->supported = information.maximum > information.minimum;
            profile->minimum = information.minimum;
            profile->maximum = information.maximum;
            profile->flat = information.flat;
            fprintf(log,
                    "analog input=%s code=%d min=%d max=%d flat=%d fuzz=%d resolution=%d\n",
                    path, code, information.minimum, information.maximum,
                    information.flat, information.fuzz, information.resolution);
        }
        ++inputs->count;
    }
    fprintf(log, "input_count=%d\n", inputs->count); fflush(log);
}

static enum action classify_stick(struct input_set *inputs, int source,
                                  const struct input_event *event)
{
    struct axis_profile *profile;
    int64_t center, half_range, threshold, value;
    int direction;
    int horizontal;
    enum action action;
    struct timespec now;
    int64_t now_ms;
    if (source < 0 || source >= inputs->count || event->code >= ABS_CNT)
        return ACTION_NONE;
    profile = &inputs->axes[source][event->code];
    if (!profile->supported) return ACTION_NONE;
    center = ((int64_t)profile->minimum + profile->maximum) / 2;
    half_range = ((int64_t)profile->maximum - profile->minimum) / 2;
    threshold = half_range / 2;
    if (threshold < (int64_t)profile->flat * 2)
        threshold = (int64_t)profile->flat * 2;
    value = event->value;
    direction = value < center - threshold ? -1 : value > center + threshold ? 1 : 0;
    if (direction == profile->direction) return ACTION_NONE;
    profile->direction = direction;
    if (direction == 0) {
        profile->repeat_action = ACTION_NONE;
        profile->repeat_at_ms = 0;
        profile->repeats_left = 0;
        return ACTION_NONE;
    }
    horizontal = event->code == ABS_X || event->code == ABS_RX ||
                 (event->code == ABS_Y && !inputs->axes[source][ABS_X].supported) ||
                 (event->code == ABS_Z && inputs->axes[source][ABS_X].supported) ||
                 (event->code == ABS_RY && !inputs->axes[source][ABS_RX].supported);
    if (horizontal) action = direction < 0 ? ACTION_LEFT : ACTION_RIGHT;
    else action = direction < 0 ? ACTION_UP : ACTION_DOWN;
    (void)clock_gettime(CLOCK_MONOTONIC, &now);
    now_ms = (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
    profile->repeat_action = action;
    profile->repeat_at_ms = now_ms + 500;
    profile->repeats_left = 4;
    return action;
}

static enum action repeat_stick(struct input_set *inputs)
{
    struct timespec now;
    int64_t now_ms;
    int source, code;
    (void)clock_gettime(CLOCK_MONOTONIC, &now);
    now_ms = (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
    for (source = 0; source < inputs->count; ++source) {
        for (code = 0; code < ABS_CNT; ++code) {
            struct axis_profile *profile = &inputs->axes[source][code];
            if (profile->direction && profile->repeat_action != ACTION_NONE &&
                profile->repeats_left > 0 &&
                now_ms >= profile->repeat_at_ms) {
                enum action action = (enum action)profile->repeat_action;
                --profile->repeats_left;
                profile->repeat_at_ms = now_ms + 250;
                if (profile->repeats_left == 0)
                    profile->repeat_action = ACTION_NONE;
                return action;
            }
        }
    }
    return ACTION_NONE;
}

static void stop_stick_repeats(struct input_set *inputs)
{
    int source, code;
    for (source = 0; source < inputs->count; ++source)
        for (code = 0; code < ABS_CNT; ++code) {
            inputs->axes[source][code].repeat_action = ACTION_NONE;
            inputs->axes[source][code].repeat_at_ms = 0;
            inputs->axes[source][code].repeats_left = 0;
        }
}

static void wifi_scan_screen(struct framebuffer *fb, struct wifi_ui *wifi, FILE *log)
{
    draw_header(fb, "WIFI");
    draw_centered(fb, 190, "SCANNING NEARBY NETWORKS", 3, color(fb, 244, 241, 228));
    draw_centered(fb, 260, "CLIENT MODE ONLY", 2, color(fb, 151, 220, 231));
    present(fb);
    (void)guide_wifi_scan(&wifi->list, log);
    draw_wifi_list(fb, wifi);
}

static void wifi_keyboard_select(struct framebuffer *fb, struct wifi_ui *wifi,
                                 enum screen *screen, FILE *log)
{
    unsigned row = wifi->cursor / 10, column = wifi->cursor % 10;
    if (row < 4) {
        if (column < keyboard_row_length(row) && wifi->password_length < GUIDE_WIFI_PASSWORD_MAX) {
            wifi->password[wifi->password_length++] = keyboard_row(wifi->page, row)[column];
            wifi->password[wifi->password_length] = '\0';
        }
        draw_wifi_keyboard(fb, wifi);
    } else if (column == 0) {
        wifi->page = wifi->page == 0 ? 1 : 0;
        draw_wifi_keyboard(fb, wifi);
    } else if (column == 1) {
        wifi->page = wifi->page == 2 ? 0 : 2;
        draw_wifi_keyboard(fb, wifi);
    } else if (column == 2) {
        if (wifi->password_length < GUIDE_WIFI_PASSWORD_MAX) {
            wifi->password[wifi->password_length++] = ' ';
            wifi->password[wifi->password_length] = '\0';
        }
        draw_wifi_keyboard(fb, wifi);
    } else if (column == 3) {
        if (wifi->password_length) wifi->password[--wifi->password_length] = '\0';
        draw_wifi_keyboard(fb, wifi);
    } else if (column == 4) {
        draw_header(fb, "WIFI");
        draw_centered(fb, 190, "CONNECTING", 5, color(fb, 245, 177, 52));
        draw_centered(fb, 275, "THIS MAY TAKE A MINUTE", 2, color(fb, 151, 220, 231));
        present(fb);
        wifi->success = guide_wifi_connect(&wifi->list.networks[wifi->list.selected],
                                           wifi->password, log, wifi->result,
                                           sizeof(wifi->result)) == 0;
        memset(wifi->password, 0, sizeof(wifi->password)); wifi->password_length = 0;
        *screen = SCREEN_WIFI_RESULT; draw_wifi_result(fb, wifi);
    } else {
        memset(wifi->password, 0, sizeof(wifi->password)); wifi->password_length = 0;
        *screen = SCREEN_WIFI_LIST; draw_wifi_list(fb, wifi);
    }
}

static int node_command(const char *command, const char *first, const char *second,
                        char *output, size_t capacity, struct node_ui *node, FILE *log)
{
    int descriptors[2], status = 0;
    pid_t child;
    size_t used = 0;
    if (pipe(descriptors) != 0) return -1;
    child = fork();
    if (child == 0) {
        (void)dup2(descriptors[1], STDOUT_FILENO);
        (void)dup2(descriptors[1], STDERR_FILENO);
        close(descriptors[0]); close(descriptors[1]);
        (void)setenv("PYTHONPATH", GUIDE_NODE_APP_DIR ":" GUIDE_WIKI_APP_DIR ":"
                     GUIDE_WIKI_APP_DIR "/runtime/python3.12/lib-dynload", 1);
        (void)setenv("LD_LIBRARY_PATH", GUIDE_WIKI_APP_DIR "/runtime/lib", 1);
        if (second)
            execl("/usr/bin/python3", "python3", GUIDE_NODE_APP_DIR "/guide_node_bridge.py",
                  command, first, second, (char *)NULL);
        else if (first)
            execl("/usr/bin/python3", "python3", GUIDE_NODE_APP_DIR "/guide_node_bridge.py",
                  command, first, (char *)NULL);
        else
            execl("/usr/bin/python3", "python3", GUIDE_NODE_APP_DIR "/guide_node_bridge.py",
                  command, (char *)NULL);
        _exit(127);
    }
    close(descriptors[1]);
    if (child < 0) { close(descriptors[0]); return -1; }
    while (used + 1 < capacity) {
        ssize_t count = read(descriptors[0], output + used, capacity - used - 1);
        if (count <= 0) break;
        used += (size_t)count;
    }
    close(descriptors[0]); output[used] = '\0';
    if (waitpid(child, &status, 0) < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        const char *error = strstr(output, "ERROR=");
        snprintf(node->message, sizeof(node->message), "%.90s",
                 error ? error + 6 : "NODE REQUEST FAILED");
        {
            char *newline = strchr(node->message, '\n');
            if (newline) *newline = '\0';
        }
        fprintf(log, "node request failed command=%s status=%d bytes=%zu\n", command,
                WIFEXITED(status) ? WEXITSTATUS(status) : -1, used); fflush(log);
        return -1;
    }
    return 0;
}

static int audio_control(const char *command, FILE *log)
{
    int descriptors[2], status = 0, volume = -1;
    pid_t child;
    char output[128] = "";
    size_t used = 0;
    if (access(GUIDE_AUDIO_CONTROL, X_OK) != 0 ||
        access(GUIDE_MEDIA_LOADER, X_OK) != 0 || pipe(descriptors) != 0)
        return -1;
    child = fork();
    if (child == 0) {
        (void)dup2(descriptors[1], STDOUT_FILENO);
        if (log) (void)dup2(fileno(log), STDERR_FILENO);
        close(descriptors[0]); close(descriptors[1]);
        if (command)
            execl(GUIDE_MEDIA_LOADER, GUIDE_MEDIA_LOADER, "--library-path",
                  GUIDE_MEDIA_DIR "/lib", GUIDE_AUDIO_CONTROL, command, (char *)NULL);
        else
            execl(GUIDE_MEDIA_LOADER, GUIDE_MEDIA_LOADER, "--library-path",
                  GUIDE_MEDIA_DIR "/lib", GUIDE_AUDIO_CONTROL, (char *)NULL);
        _exit(127);
    }
    close(descriptors[1]);
    if (child < 0) { close(descriptors[0]); return -1; }
    while (used + 1 < sizeof(output)) {
        ssize_t count = read(descriptors[0], output + used, sizeof(output) - used - 1);
        if (count <= 0) break;
        used += (size_t)count;
    }
    close(descriptors[0]); output[used] = '\0';
    if (waitpid(child, &status, 0) >= 0 && WIFEXITED(status) && WEXITSTATUS(status) == 0) {
        char *value = strstr(output, "VOLUME=");
        if (value) volume = atoi(value + 7);
    }
    if (volume < 0 || volume > 100) volume = -1;
    fprintf(log, "audio control command=%s volume=%d status=%d\n",
            command ? command : "query", volume,
            WIFEXITED(status) ? WEXITSTATUS(status) : -1);
    fflush(log);
    return volume;
}

static int node_discover(struct node_ui *node, FILE *log)
{
    char output[4096], *line, *save = NULL;
    node->count = 0; node->selected = 0; node->message[0] = '\0';
    node->success = 0; node->trusted = 0; node->paired_name[0] = '\0';
    if (node_command("discover", NULL, NULL, output, sizeof(output), node, log) != 0)
        return -1;
    line = strtok_r(output, "\n", &save);
    if (!line || strcmp(line, "GUIDE-NODES-1") != 0) {
        snprintf(node->message, sizeof(node->message), "UNRECOGNIZED NODE RESPONSE");
        return -1;
    }
    while ((line = strtok_r(NULL, "\n", &save)) != NULL) {
        char *separator;
        unsigned index;
        if (strncmp(line, "TRUSTED=", 8) == 0) {
            index = (unsigned)strtoul(line + 8, NULL, 10);
            if (index < node->count) {
                node->candidates[index].trusted = 1;
                node->selected = index;
                node->success = 1; node->trusted = 1;
                snprintf(node->paired_name, sizeof(node->paired_name), "%s",
                         node->candidates[index].name);
            }
            continue;
        }
        if (strncmp(line, "NODE=", 5) != 0 || !(separator = strchr(line + 5, '\t')))
            continue;
        if (node->count >= GUIDE_NODE_MAX) continue;
        *separator = '\0'; index = (unsigned)strtoul(line + 5, NULL, 10);
        if (index != node->count) continue;
        snprintf(node->candidates[node->count].name,
                 sizeof(node->candidates[node->count].name), "%s", separator + 1);
        ++node->count;
    }
    fprintf(log, "node discovery success count=%u\n", node->count); fflush(log);
    return 0;
}

static int node_pair(struct node_ui *node, FILE *log)
{
    char output[4096], index[8], *line, *save = NULL;
    snprintf(index, sizeof(index), "%u", node->selected);
    node->success = 0; node->trusted = 0; node->message[0] = '\0';
    if (node_command("pair", index, node->code, output, sizeof(output), node, log) != 0)
        return -1;
    line = strtok_r(output, "\n", &save);
    if (!line || strcmp(line, "GUIDE-NODE-PAIRED-1") != 0) {
        snprintf(node->message, sizeof(node->message), "UNRECOGNIZED PAIRING RESPONSE");
        return -1;
    }
    while ((line = strtok_r(NULL, "\n", &save)) != NULL) {
        if (strncmp(line, "NAME=", 5) == 0)
            snprintf(node->paired_name, sizeof(node->paired_name), "%s", line + 5);
        else if (strncmp(line, "ANDROID=", 8) == 0)
            snprintf(node->android_state, sizeof(node->android_state), "%s", line + 8);
    }
    if (!node->paired_name[0]) {
        snprintf(node->message, sizeof(node->message), "PAIRING RESPONSE WAS INCOMPLETE");
        return -1;
    }
    node->success = 1;
    memset(node->code, 0, sizeof(node->code)); node->code_length = 0;
    fprintf(log, "node pairing success name=%s\n", node->paired_name); fflush(log);
    return 0;
}

static int node_trust(struct node_ui *node, FILE *log)
{
    char output[1024];
    node->message[0] = '\0';
    if (node_command("trust", NULL, NULL, output, sizeof(output), node, log) != 0)
        return -1;
    if (strncmp(output, "GUIDE-NODE-TRUSTED-1\n", 21) != 0) {
        snprintf(node->message, sizeof(node->message), "UNRECOGNIZED TRUST RESPONSE");
        return -1;
    }
    node->trusted = 1;
    if (node->selected < node->count) node->candidates[node->selected].trusted = 1;
    fprintf(log, "node trust completed name=%s\n", node->paired_name); fflush(log);
    return 0;
}

static int node_media_refresh(struct node_ui *node, FILE *log)
{
    char output[32768], *line, *save = NULL;
    memset(node->media, 0, sizeof(node->media));
    node->media_count = 0; node->media_total = 0; node->media_selected = 0;
    node->message[0] = '\0';
    if (node_command("media", NULL, NULL, output, sizeof(output), node, log) != 0)
        return -1;
    line = strtok_r(output, "\n", &save);
    if (!line || strcmp(line, "GUIDE-MEDIA-1") != 0) {
        snprintf(node->message, sizeof(node->message), "UNRECOGNIZED MEDIA RESPONSE");
        return -1;
    }
    while ((line = strtok_r(NULL, "\n", &save)) != NULL) {
        if (strncmp(line, "TOTAL=", 6) == 0) {
            node->media_total = (unsigned)strtoul(line + 6, NULL, 10);
        } else if (strncmp(line, "MEDIA=", 6) == 0 &&
                   node->media_count < GUIDE_MEDIA_MAX) {
            char *kind, *size, *name;
            unsigned index;
            kind = strchr(line + 6, '\t');
            if (!kind) continue;
            *kind++ = '\0';
            size = strchr(kind, '\t');
            if (!size) continue;
            *size++ = '\0';
            name = strchr(size, '\t');
            if (!name) continue;
            *name++ = '\0';
            index = (unsigned)strtoul(line + 6, NULL, 10);
            if (index != node->media_count ||
                (strcmp(kind, "audio") != 0 && strcmp(kind, "video") != 0)) continue;
            snprintf(node->media[index].kind, sizeof(node->media[index].kind), "%s", kind);
            node->media[index].size = strtoull(size, NULL, 10);
            snprintf(node->media[index].name, sizeof(node->media[index].name), "%s", name);
            ++node->media_count;
        } else if (strncmp(line, "SUBTITLE=", 9) == 0) {
            char *track, *label;
            unsigned index, track_index;
            track = strchr(line + 9, '\t');
            if (!track) continue;
            *track++ = '\0';
            label = strchr(track, '\t');
            if (!label) continue;
            *label++ = '\0';
            index = (unsigned)strtoul(line + 9, NULL, 10);
            track_index = (unsigned)strtoul(track, NULL, 10);
            if (index >= node->media_count || track_index >= GUIDE_SUBTITLE_MAX) continue;
            snprintf(node->media[index].subtitles[track_index],
                     sizeof(node->media[index].subtitles[track_index]), "%s", label);
            if (node->media[index].subtitle_count <= track_index)
                node->media[index].subtitle_count = track_index + 1;
        }
    }
    fprintf(log, "node media refresh count=%u total=%u\n",
            node->media_count, node->media_total); fflush(log);
    return 0;
}

static int node_media_start(struct node_ui *node, FILE *log)
{
    char index[16];
    pid_t child;
    int descriptor;
    if (node->media_selected >= node->media_count) return -1;
    snprintf(index, sizeof(index), "%u", node->media_selected);
    child = fork();
    if (child == 0) {
        (void)setpgid(0, 0);
        descriptor = open("/var/log/guide-media.log",
                          O_WRONLY | O_CREAT | O_APPEND | O_NOFOLLOW, 0600);
        if (descriptor >= 0) {
            (void)dup2(descriptor, STDOUT_FILENO);
            (void)dup2(descriptor, STDERR_FILENO);
            if (descriptor > STDERR_FILENO) close(descriptor);
        }
        (void)setenv("PYTHONPATH", GUIDE_NODE_APP_DIR ":" GUIDE_WIKI_APP_DIR ":"
                     GUIDE_WIKI_APP_DIR "/runtime/python3.12/lib-dynload", 1);
        (void)setenv("LD_LIBRARY_PATH", GUIDE_WIKI_APP_DIR "/runtime/lib", 1);
        execl("/usr/bin/python3", "python3", GUIDE_NODE_APP_DIR "/guide_node_bridge.py",
              "play", index, (char *)NULL);
        _exit(127);
    }
    if (child < 0) {
        snprintf(node->message, sizeof(node->message), "COULD NOT START PLAYER");
        return -1;
    }
    (void)setpgid(child, child);
    node->playback_pid = child;
    node->playback_paused = 0;
    node->subtitle_current = -1;
    node->subtitle_menu_selected = 0;
    fprintf(log, "node media playback started pid=%ld index=%u name=%s\n",
            (long)child, node->media_selected, node->media[node->media_selected].name);
    fflush(log);
    return 0;
}

static void node_media_stop(struct node_ui *node, FILE *log)
{
    if (node->playback_pid > 0) {
        (void)kill(-node->playback_pid, SIGCONT);
        (void)kill(-node->playback_pid, SIGTERM);
        fprintf(log, "node media playback stop requested pid=%ld\n",
                (long)node->playback_pid); fflush(log);
    }
    node->playback_paused = 0;
}

static int node_media_control(struct node_ui *node, const char *command, FILE *log)
{
    char path[96];
    int descriptor;
    size_t length;
    if (node->playback_pid <= 0 || !command || strchr(command, '\n')) return -1;
    snprintf(path, sizeof(path), "/run/guideos-media-control-%ld", (long)node->playback_pid);
    descriptor = open(path, O_WRONLY | O_APPEND | O_NOFOLLOW);
    if (descriptor < 0) {
        fprintf(log, "media control unavailable pid=%ld error=%s\n",
                (long)node->playback_pid, strerror(errno)); fflush(log);
        return -1;
    }
    length = strlen(command);
    if (write(descriptor, command, length) != (ssize_t)length ||
        write(descriptor, "\n", 1) != 1) {
        close(descriptor); return -1;
    }
    close(descriptor);
    fprintf(log, "media control pid=%ld command=%s\n", (long)node->playback_pid, command);
    fflush(log); return 0;
}

static unsigned node_keypad_move(unsigned key, int horizontal, int vertical)
{
    unsigned row = key / 3, column = key % 3;
    if (horizontal < 0) column = column == 0 ? 2 : column - 1;
    else if (horizontal > 0) column = (column + 1) % 3;
    if (vertical < 0) row = row == 0 ? 3 : row - 1;
    else if (vertical > 0) row = (row + 1) % 4;
    return row * 3 + column;
}

static int node_keypad_select(struct node_ui *node)
{
    static const char digits[] = "123456789\0";
    if (node->keypad < 9) {
        if (node->code_length < 6) {
            node->code[node->code_length++] = digits[node->keypad];
            node->code[node->code_length] = '\0';
        }
    } else if (node->keypad == 9) {
        if (node->code_length) node->code[--node->code_length] = '\0';
    } else if (node->keypad == 10) {
        if (node->code_length < 6) {
            node->code[node->code_length++] = '0';
            node->code[node->code_length] = '\0';
        }
    } else return node->code_length == 6;
    return 0;
}

static int wikipedia_command(const char *command, const char *argument,
                             char *output, size_t capacity,
                             struct wikipedia_ui *wiki, FILE *log)
{
    int descriptors[2], status = 0;
    pid_t child;
    size_t used = 0;
    if (pipe(descriptors) != 0) return -1;
    child = fork();
    if (child == 0) {
        (void)dup2(descriptors[1], STDOUT_FILENO);
        (void)dup2(descriptors[1], STDERR_FILENO);
        close(descriptors[0]); close(descriptors[1]);
        (void)setenv("PYTHONPATH", GUIDE_WIKI_APP_DIR ":" GUIDE_WIKI_APP_DIR "/runtime/python3.12/lib-dynload", 1);
        (void)setenv("LD_LIBRARY_PATH", GUIDE_WIKI_APP_DIR "/runtime/lib", 1);
        (void)setenv("SSL_CERT_FILE", GUIDE_WIKI_APP_DIR "/runtime/certs/ca-certificates.crt", 1);
        execl("/usr/bin/python3", "python3",
              GUIDE_WIKI_APP_DIR "/guide_wikipedia_bridge.py",
              command, argument, (char *)NULL);
        _exit(127);
    }
    close(descriptors[1]);
    if (child < 0) { close(descriptors[0]); return -1; }
    while (used + 1 < capacity) {
        ssize_t count = read(descriptors[0], output + used, capacity - used - 1);
        if (count <= 0) break;
        used += (size_t)count;
    }
    close(descriptors[0]); output[used] = '\0';
    if (waitpid(child, &status, 0) < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        const char *error = strstr(output, "ERROR=");
        snprintf(wiki->message, sizeof(wiki->message), "%.80s",
                 error ? error + 6 : "WIKIPEDIA REQUEST FAILED");
        fprintf(log, "wikipedia request failed status=%d bytes=%zu\n",
                WIFEXITED(status) ? WEXITSTATUS(status) : -1, used); fflush(log);
        return -1;
    }
    return 0;
}

static int wikipedia_search(struct wikipedia_ui *wiki, FILE *log)
{
    char output[8192], *line, *save = NULL;
    wiki->result_count = 0; wiki->selected_result = 0;
    if (wikipedia_command("search", wiki->query, output, sizeof(output), wiki, log) != 0)
        return -1;
    line = strtok_r(output, "\n", &save);
    if (!line || strcmp(line, "GUIDE-WIKIPEDIA-SEARCH-1") != 0) {
        snprintf(wiki->message, sizeof(wiki->message), "UNRECOGNIZED WIKIPEDIA RESPONSE");
        return -1;
    }
    while ((line = strtok_r(NULL, "\n", &save)) != NULL &&
           wiki->result_count < GUIDE_WIKI_RESULT_MAX) {
        char *separator;
        struct wikipedia_result *item;
        if (strncmp(line, "RESULT=", 7) != 0 || !(separator = strchr(line + 7, '\t')))
            continue;
        *separator = '\0'; item = &wiki->results[wiki->result_count++];
        item->word_count = (unsigned)strtoul(line + 7, NULL, 10);
        snprintf(item->title, sizeof(item->title), "%s", separator + 1);
    }
    wiki->message[0] = '\0';
    fprintf(log, "wikipedia search success results=%u\n", wiki->result_count); fflush(log);
    return 0;
}

static int wikipedia_fetch_article(struct wikipedia_ui *wiki, const char *requested,
                                   FILE *log)
{
    char *output = malloc(GUIDE_WIKI_TEXT_MAX + GUIDE_WIKI_PROTOCOL_MARGIN);
    const char *title, *body, *line_end, *cursor;
    size_t body_length;
    if (!output) { snprintf(wiki->message, sizeof(wiki->message), "NOT ENOUGH MEMORY"); return -1; }
    if (wikipedia_command("article", requested, output,
                          GUIDE_WIKI_TEXT_MAX + GUIDE_WIKI_PROTOCOL_MARGIN,
                          wiki, log) != 0) { free(output); return -1; }
    if (strncmp(output, "GUIDE-WIKIPEDIA-ARTICLE-2\nTITLE=", 32) != 0) {
        snprintf(wiki->message, sizeof(wiki->message), "UNRECOGNIZED ARTICLE RESPONSE");
        free(output); return -1;
    }
    title = output + 32;
    line_end = strchr(title, '\n');
    if (!line_end || strncmp(line_end + 1, "SOURCE=", 7) != 0 ||
        !(body = strstr(line_end + 1, "\n\n"))) {
        snprintf(wiki->message, sizeof(wiki->message), "INCOMPLETE ARTICLE RESPONSE");
        free(output); return -1;
    }
    {
        size_t title_length = (size_t)(line_end - title);
        if (title_length >= sizeof(wiki->title)) title_length = sizeof(wiki->title) - 1;
        memcpy(wiki->title, title, title_length); wiki->title[title_length] = '\0';
    }
    wiki->link_count = 0; wiki->selected_link = 0;
    cursor = strchr(line_end + 1, '\n');
    if (!cursor) { snprintf(wiki->message, sizeof(wiki->message), "INCOMPLETE ARTICLE LINKS"); free(output); return -1; }
    ++cursor;
    while (cursor < body && wiki->link_count < GUIDE_WIKI_LINK_MAX) {
        const char *link_end = strchr(cursor, '\n');
        size_t link_length;
        if (!link_end || link_end > body) link_end = body;
        if (strncmp(cursor, "LINK=", 5) == 0) {
            link_length = (size_t)(link_end - (cursor + 5));
            if (link_length >= sizeof(wiki->links[0].title))
                link_length = sizeof(wiki->links[0].title) - 1;
            memcpy(wiki->links[wiki->link_count].title, cursor + 5, link_length);
            wiki->links[wiki->link_count].title[link_length] = '\0';
            if (link_length) ++wiki->link_count;
        }
        cursor = link_end + 1;
    }
    body += 2;
    body_length = strlen(body);
    if (body_length > GUIDE_WIKI_TEXT_MAX) body_length = GUIDE_WIKI_TEXT_MAX;
    if (!wiki->text) wiki->text = malloc(GUIDE_WIKI_TEXT_MAX + 1);
    if (!wiki->text) { snprintf(wiki->message, sizeof(wiki->message), "NOT ENOUGH MEMORY"); free(output); return -1; }
    memcpy(wiki->text, body, body_length); wiki->text[body_length] = '\0';
    wiki->text_length = body_length;
    wiki->page = 0; wiki->known_pages = 1; wiki->page_offsets[0] = 0;
    wiki->message[0] = '\0';
    fprintf(log, "wikipedia request success title=%s bytes=%zu\n", wiki->title,
            wiki->text_length); fflush(log);
    free(output);
    return 0;
}

static void wikipedia_keyboard_select(struct framebuffer *fb,
                                      struct wikipedia_ui *wiki,
                                      enum screen *screen, FILE *log)
{
    unsigned row = wiki->cursor / 10, column = wiki->cursor % 10;
    if (row < 4) {
        if (column < keyboard_row_length(row) && wiki->query_length < GUIDE_WIKI_QUERY_MAX) {
            wiki->query[wiki->query_length++] = keyboard_row(wiki->keyboard_page, row)[column];
            wiki->query[wiki->query_length] = '\0';
        }
        draw_wikipedia_keyboard(fb, wiki);
    } else if (column == 0) {
        wiki->keyboard_page = wiki->keyboard_page == 0 ? 1 : 0;
        draw_wikipedia_keyboard(fb, wiki);
    } else if (column == 1) {
        wiki->keyboard_page = wiki->keyboard_page == 2 ? 0 : 2;
        draw_wikipedia_keyboard(fb, wiki);
    } else if (column == 2) {
        if (wiki->query_length < GUIDE_WIKI_QUERY_MAX) {
            wiki->query[wiki->query_length++] = ' '; wiki->query[wiki->query_length] = '\0';
        }
        draw_wikipedia_keyboard(fb, wiki);
    } else if (column == 3) {
        if (wiki->query_length) wiki->query[--wiki->query_length] = '\0';
        draw_wikipedia_keyboard(fb, wiki);
    } else if (column == 4) {
        if (!wiki->query_length) { snprintf(wiki->message, sizeof(wiki->message), "ENTER A SEARCH"); return; }
        draw_header(fb, "WIKIPEDIA");
        draw_centered(fb, 180, "SEARCHING", 5, color(fb, 245, 177, 52));
        draw_centered(fb, 270, "ONE VERIFIED HTTPS REQUEST", 2,
                      color(fb, 151, 220, 231)); present(fb);
        if (wikipedia_search(wiki, log) == 0) {
            *screen = SCREEN_WIKIPEDIA_RESULTS; draw_wikipedia_results(fb, wiki);
        } else {
            *screen = SCREEN_WIKIPEDIA_HOME; draw_wikipedia_home(fb, wiki);
        }
    } else {
        *screen = SCREEN_WIKIPEDIA_HOME; draw_wikipedia_home(fb, wiki);
    }
}

static enum action classify_event(struct input_set *inputs, int source,
                                  const struct input_event *event)
{
    if (event->type == EV_KEY && event->value == 1) {
        if (event->code == KEY_POWER) return ACTION_POWER;
        if (event->code == KEY_VOLUMEDOWN) return ACTION_VOLUME_DOWN;
        if (event->code == KEY_VOLUMEUP) return ACTION_VOLUME_UP;
        if (event->code == KEY_UP || event->code == BTN_DPAD_UP) return ACTION_UP;
        if (event->code == KEY_DOWN || event->code == BTN_DPAD_DOWN) return ACTION_DOWN;
        if (event->code == KEY_LEFT || event->code == BTN_DPAD_LEFT) return ACTION_LEFT;
        if (event->code == KEY_RIGHT || event->code == BTN_DPAD_RIGHT) return ACTION_RIGHT;
        if (event->code == KEY_ENTER || event->code == BTN_SOUTH) return ACTION_OPEN;
        if (event->code == KEY_ESC || event->code == BTN_EAST) return ACTION_BACK;
        if (event->code == BTN_NORTH) return ACTION_SPACE;
        if (event->code == BTN_TL) return ACTION_L1;
        if (event->code == BTN_TR) return ACTION_R1;
        if (event->code == BTN_TL2) return ACTION_L2;
        if (event->code == BTN_TR2) return ACTION_R2;
        return ACTION_OTHER;
    }
    if (event->type == EV_ABS && event->code == ABS_HAT0Y) {
        if (event->value < 0) return ACTION_UP;
        if (event->value > 0) return ACTION_DOWN;
    }
    if (event->type == EV_ABS && event->code == ABS_HAT0X) {
        if (event->value < 0) return ACTION_LEFT;
        if (event->value > 0) return ACTION_RIGHT;
    }
    if (event->type == EV_ABS &&
        (event->code == ABS_X || event->code == ABS_Y || event->code == ABS_Z ||
         event->code == ABS_RX || event->code == ABS_RY || event->code == ABS_RZ))
        return classify_stick(inputs, source, event);
    return ACTION_NONE;
}

static int next_event(struct input_set *inputs, struct input_event *event, int *source)
{
    int ready, i;
    if (inputs->count == 0) { struct timespec pause = {0, 50000000}; nanosleep(&pause, NULL); return 0; }
    ready = poll(inputs->pollfds, (nfds_t)inputs->count, 50);
    if (ready <= 0) return 0;
    for (i = 0; i < inputs->count; ++i)
        if ((inputs->pollfds[i].revents & POLLIN) &&
            read(inputs->pollfds[i].fd, event, sizeof(*event)) == (ssize_t)sizeof(*event)) {
            *source = i;
            return 1;
        }
    return 0;
}

static void run_shell(struct framebuffer *fb, FILE *log)
{
    struct input_set inputs = {0};
    struct guide_cartridge_catalog catalog = {0};
    struct wifi_ui wifi = {0};
    struct node_ui node = {0};
    struct wikipedia_ui wiki = {0};
    enum screen screen = SCREEN_MENU;
    enum screen previous_screen = SCREEN_MENU;
    unsigned selected = 0, idle_scans = 0;
    int link_state = guide_wifi_link_up();
    long long volume_indicator_until = 0;
    int volume_indicator_paused_video = 0;
    char install_message[96] = "", developer_message[96] = "";
    int install_success = 0;
    guide_volume_percent = audio_control(NULL, log);
    open_inputs(&inputs, log); draw_menu(fb, selected);
    for (;;) {
        struct input_event event;
        enum action action;
        int source = -1;
        int received = next_event(&inputs, &event, &source);
        if (!received) {
            int current_link = guide_wifi_link_up();
            if (node.playback_pid > 0) {
                int playback_status = 0;
                pid_t ended = waitpid(node.playback_pid, &playback_status, WNOHANG);
                if (ended == node.playback_pid || (ended < 0 && errno == ECHILD)) {
                    fprintf(log, "node media playback ended status=%d\n", playback_status);
                    fflush(log);
                    node.playback_pid = 0; node.playback_paused = 0;
                    if (screen == SCREEN_MEDIA_PLAYING || screen == SCREEN_MEDIA_SUBTITLES) {
                        snprintf(node.message, sizeof(node.message),
                                 WIFEXITED(playback_status) && WEXITSTATUS(playback_status) == 0 ?
                                 "PLAYBACK COMPLETE" : "PLAYBACK STOPPED");
                        screen = SCREEN_MEDIA_LIST; draw_media_list(fb, &node);
                    }
                }
            }
            if (node.playback_pid <= 0) (void)waitpid(-1, NULL, WNOHANG);
            if (volume_indicator_until &&
                monotonic_milliseconds() >= volume_indicator_until) {
                volume_indicator_until = 0;
                if (volume_indicator_paused_video && node.playback_pid > 0)
                    (void)kill(-node.playback_pid, SIGCONT);
                volume_indicator_paused_video = 0;
                if (screen != SCREEN_MEDIA_PLAYING)
                    redraw_screen(fb, screen, selected, (unsigned)inputs.count,
                                  &catalog, install_message, install_success,
                                  &wifi, &node, &wiki);
            }
            if (inputs.count == 0 && ++idle_scans % 60 == 0) open_inputs(&inputs, log);
            if (current_link != link_state && screen != SCREEN_SHUTDOWN) {
                link_state = current_link;
                if (!current_link && guide_developer_link_installed())
                    (void)developer_link_control("stop", log);
                if (!current_link && node.playback_pid > 0)
                    node_media_stop(&node, log);
                redraw_screen(fb, screen, selected, (unsigned)inputs.count,
                              &catalog, install_message, install_success, &wifi, &node, &wiki);
            }
            action = repeat_stick(&inputs);
            if (action == ACTION_NONE) continue;
            memset(&event, 0, sizeof(event));
        } else {
            idle_scans = 0; action = classify_event(&inputs, source, &event);
        }
        if (received && (event.type == EV_KEY || event.type == EV_ABS)) {
            fprintf(log, "event input=%d type=%u code=%u value=%d action=%d\n",
                    source, event.type, event.code, event.value, action);
            fflush(log);
        }
        if (volume_indicator_until && action != ACTION_NONE &&
            action != ACTION_VOLUME_DOWN && action != ACTION_VOLUME_UP) {
            volume_indicator_until = 0;
            if (volume_indicator_paused_video && node.playback_pid > 0)
                (void)kill(-node.playback_pid, SIGCONT);
            volume_indicator_paused_video = 0;
        }
        if (action == ACTION_NONE) {
            if (screen == SCREEN_INPUT && (event.type == EV_KEY || event.type == EV_ABS))
                draw_input_test(fb, event.type, event.code, event.value);
            continue;
        }
        if (action == ACTION_VOLUME_DOWN || action == ACTION_VOLUME_UP) {
            int adjusted = audio_control(action == ACTION_VOLUME_UP ?
                                         "--volume-up" : "--volume-down", log);
            if (adjusted >= 0) guide_volume_percent = adjusted;
            if (screen == SCREEN_MEDIA_PLAYING && node.playback_pid > 0 &&
                node.media_selected < node.media_count &&
                strcmp(node.media[node.media_selected].kind, "video") == 0 &&
                !node.playback_paused && !volume_indicator_paused_video &&
                kill(-node.playback_pid, SIGSTOP) == 0)
                volume_indicator_paused_video = 1;
            draw_volume_indicator(fb, guide_volume_percent);
            volume_indicator_until = monotonic_milliseconds() + 900;
        } else if (action == ACTION_POWER && screen != SCREEN_SHUTDOWN) {
            if (node.playback_pid > 0) node_media_stop(&node, log);
            previous_screen = screen;
            screen = SCREEN_SHUTDOWN;
            draw_shutdown_confirm(fb);
        } else if (screen == SCREEN_SHUTDOWN) {
            if (action == ACTION_OPEN) safe_shutdown(fb, log, &catalog);
            else if (action == ACTION_BACK || action == ACTION_POWER) {
                screen = previous_screen;
                redraw_screen(fb, screen, selected, (unsigned)inputs.count,
                              &catalog, install_message, install_success, &wifi, &node, &wiki);
            }
        } else if (screen == SCREEN_MENU) {
            if (action == ACTION_UP) { selected = selected == 0 ? 8 : selected - 1; draw_menu(fb, selected); }
            else if (action == ACTION_DOWN) { selected = (selected + 1) % 9; draw_menu(fb, selected); }
            else if (action == ACTION_OPEN) {
                screen = selected == 0 ? SCREEN_CARTRIDGE_LIST : selected == 1 ? SCREEN_WIFI_LIST :
                         selected == 2 ? SCREEN_NODE_LIST : selected == 3 ? SCREEN_MEDIA_LIST :
                         selected == 4 ? SCREEN_WIKIPEDIA_HOME : selected == 5 ? SCREEN_DEVELOPER_LINK :
                         selected == 6 ? SCREEN_DISPLAY : selected == 7 ? SCREEN_INPUT : SCREEN_SYSTEM;
                if (screen == SCREEN_CARTRIDGE_LIST) {
                    /* A held stick must not carry its repeat into a new menu. */
                    stop_stick_repeats(&inputs);
                    guide_cartridge_scan(&catalog, log);
                    draw_cartridge_list(fb, &catalog);
                } else if (screen == SCREEN_WIFI_LIST) {
                    wifi_scan_screen(fb, &wifi, log);
                } else if (screen == SCREEN_NODE_LIST) {
                    stop_stick_repeats(&inputs);
                    draw_header(fb, "NODES");
                    draw_centered(fb, 190, guide_wifi_link_up() ? "SEARCHING THIS NETWORK" :
                                  "CONNECT WI-FI FIRST", 4, color(fb, 245, 177, 52));
                    present(fb);
                    if (guide_wifi_link_up()) (void)node_discover(&node, log);
                    draw_node_list(fb, &node);
                } else if (screen == SCREEN_MEDIA_LIST) {
                    stop_stick_repeats(&inputs);
                    draw_header(fb, "NODE MEDIA");
                    draw_centered(fb, 190, guide_wifi_link_up() ? "READING MEDIA LIBRARY" :
                                  "CONNECT WI-FI FIRST", 4, color(fb, 245, 177, 52));
                    present(fb);
                    if (guide_wifi_link_up()) (void)node_media_refresh(&node, log);
                    else snprintf(node.message, sizeof(node.message), "CONNECT WI-FI FIRST");
                    draw_media_list(fb, &node);
                } else if (screen == SCREEN_DEVELOPER_LINK) {
                    developer_message[0] = '\0';
                    draw_developer_link(fb, log, developer_message);
                } else if (screen == SCREEN_WIKIPEDIA_HOME) {
                    wiki.message[0] = '\0'; draw_wikipedia_home(fb, &wiki);
                } else if (screen == SCREEN_DISPLAY) draw_display_test(fb);
                else if (screen == SCREEN_INPUT) draw_input_test(fb, 0, 0, 0);
                else draw_system_info(fb, (unsigned)inputs.count);
            }
        } else if (screen == SCREEN_NODE_LIST &&
                   (action == ACTION_UP || action == ACTION_DOWN ||
                    action == ACTION_LEFT || action == ACTION_RIGHT)) {
            unsigned total = node.count + 1;
            if (action == ACTION_UP || action == ACTION_LEFT)
                node.selected = node.selected == 0 ? total - 1 : node.selected - 1;
            else node.selected = (node.selected + 1) % total;
            draw_node_list(fb, &node);
        } else if (screen == SCREEN_NODE_LIST && action == ACTION_OPEN) {
            if (!guide_wifi_link_up()) {
                snprintf(node.message, sizeof(node.message), "CONNECT WI-FI FIRST");
                draw_node_list(fb, &node);
            } else if (node.selected < node.count) {
                if (node.candidates[node.selected].trusted && node.success) {
                    screen = SCREEN_NODE_RESULT; draw_node_result(fb, &node);
                } else {
                    node.keypad = 0; node.code_length = 0; node.code[0] = '\0'; node.message[0] = '\0';
                    screen = SCREEN_NODE_PAIR; draw_node_pair(fb, &node);
                }
            } else {
                draw_header(fb, "NODES");
                draw_centered(fb, 190, "SEARCHING THIS NETWORK", 4,
                              color(fb, 245, 177, 52)); present(fb);
                (void)node_discover(&node, log); draw_node_list(fb, &node);
            }
        } else if (screen == SCREEN_NODE_PAIR && action == ACTION_BACK) {
            memset(node.code, 0, sizeof(node.code)); node.code_length = 0;
            screen = SCREEN_NODE_LIST; draw_node_list(fb, &node);
        } else if (screen == SCREEN_NODE_PAIR && action == ACTION_LEFT) {
            node.keypad = node_keypad_move(node.keypad, -1, 0); draw_node_pair(fb, &node);
        } else if (screen == SCREEN_NODE_PAIR && action == ACTION_RIGHT) {
            node.keypad = node_keypad_move(node.keypad, 1, 0); draw_node_pair(fb, &node);
        } else if (screen == SCREEN_NODE_PAIR && action == ACTION_UP) {
            node.keypad = node_keypad_move(node.keypad, 0, -1); draw_node_pair(fb, &node);
        } else if (screen == SCREEN_NODE_PAIR && action == ACTION_DOWN) {
            node.keypad = node_keypad_move(node.keypad, 0, 1); draw_node_pair(fb, &node);
        } else if (screen == SCREEN_NODE_PAIR && action == ACTION_OPEN) {
            if (node_keypad_select(&node)) {
                draw_header(fb, "NODE LINK");
                draw_centered(fb, 190, "PAIRING", 5, color(fb, 245, 177, 52));
                draw_centered(fb, 275, "LOCAL DEVELOPMENT LINK", 2,
                              color(fb, 151, 220, 231)); present(fb);
                node.success = node_pair(&node, log) == 0;
                screen = SCREEN_NODE_RESULT; draw_node_result(fb, &node);
            } else draw_node_pair(fb, &node);
        } else if (screen == SCREEN_NODE_RESULT && action == ACTION_BACK) {
            screen = SCREEN_NODE_LIST; draw_node_list(fb, &node);
        } else if (screen == SCREEN_NODE_RESULT && action == ACTION_OPEN && node.success) {
            draw_header(fb, "NODE MEDIA");
            draw_centered(fb, 190, "READING MEDIA LIBRARY", 4,
                          color(fb, 245, 177, 52)); present(fb);
            (void)node_media_refresh(&node, log);
            screen = SCREEN_MEDIA_LIST; draw_media_list(fb, &node);
        } else if (screen == SCREEN_NODE_RESULT && action == ACTION_SPACE &&
                   node.success && !node.trusted) {
            draw_header(fb, "NODE TRUST");
            draw_centered(fb, 170, "REQUESTING TRUST", 4,
                          color(fb, 245, 177, 52));
            draw_centered(fb, 252, "THE NODE MUST APPROVE", 2,
                          color(fb, 151, 220, 231)); present(fb);
            (void)node_trust(&node, log);
            draw_node_result(fb, &node);
        } else if (screen == SCREEN_MEDIA_LIST &&
                   (action == ACTION_UP || action == ACTION_DOWN ||
                    action == ACTION_LEFT || action == ACTION_RIGHT)) {
            if (node.media_count) {
                if (action == ACTION_UP || action == ACTION_LEFT)
                    node.media_selected = node.media_selected == 0 ?
                                          node.media_count - 1 : node.media_selected - 1;
                else node.media_selected = (node.media_selected + 1) % node.media_count;
            }
            draw_media_list(fb, &node);
        } else if (screen == SCREEN_MEDIA_LIST && action == ACTION_OPEN) {
            if (!node.media_count) {
                (void)node_media_refresh(&node, log); draw_media_list(fb, &node);
            } else {
                draw_media_starting(fb, &node);
                if (node_media_start(&node, log) == 0) screen = SCREEN_MEDIA_PLAYING;
                else draw_media_list(fb, &node);
            }
        } else if (screen == SCREEN_MEDIA_PLAYING && action == ACTION_OPEN) {
            node_media_stop(&node, log);
        } else if (screen == SCREEN_MEDIA_PLAYING && action == ACTION_BACK &&
                   node.playback_pid > 0) {
            if (node_media_control(&node, "pause", log) == 0)
                node.playback_paused = !node.playback_paused;
        } else if (screen == SCREEN_MEDIA_PLAYING && action == ACTION_L1) {
            (void)node_media_control(&node, "rate:-2", log);
            node.playback_paused = 0;
        } else if (screen == SCREEN_MEDIA_PLAYING && action == ACTION_R1) {
            (void)node_media_control(&node, "rate:2", log);
            node.playback_paused = 0;
        } else if (screen == SCREEN_MEDIA_PLAYING && action == ACTION_L2) {
            (void)node_media_control(&node, "seek:-10", log);
        } else if (screen == SCREEN_MEDIA_PLAYING && action == ACTION_R2) {
            (void)node_media_control(&node, "seek:10", log);
        } else if (screen == SCREEN_MEDIA_PLAYING && action == ACTION_SPACE &&
                   node.media[node.media_selected].subtitle_count > 0) {
            node.subtitle_menu_selected = (unsigned)(node.subtitle_current + 1);
            node.subtitle_resume_after_menu = !node.playback_paused;
            if (node.subtitle_resume_after_menu &&
                node_media_control(&node, "pause", log) == 0)
                node.playback_paused = 1;
            screen = SCREEN_MEDIA_SUBTITLES;
            draw_media_subtitles(fb, &node);
        } else if (screen == SCREEN_MEDIA_SUBTITLES &&
                   (action == ACTION_UP || action == ACTION_DOWN)) {
            unsigned total = node.media[node.media_selected].subtitle_count + 1;
            if (action == ACTION_UP)
                node.subtitle_menu_selected = node.subtitle_menu_selected == 0 ?
                                              total - 1 : node.subtitle_menu_selected - 1;
            else node.subtitle_menu_selected = (node.subtitle_menu_selected + 1) % total;
            draw_media_subtitles(fb, &node);
        } else if (screen == SCREEN_MEDIA_SUBTITLES && action == ACTION_OPEN) {
            char command[32];
            node.subtitle_current = (int)node.subtitle_menu_selected - 1;
            snprintf(command, sizeof(command), "subtitle:%d", node.subtitle_current);
            (void)node_media_control(&node, command, log);
            if (node.subtitle_resume_after_menu) {
                (void)node_media_control(&node, "pause", log);
                node.playback_paused = 0;
            }
            screen = SCREEN_MEDIA_PLAYING;
        } else if (screen == SCREEN_MEDIA_SUBTITLES && action == ACTION_BACK) {
            if (node.subtitle_resume_after_menu) {
                (void)node_media_control(&node, "pause", log);
                node.playback_paused = 0;
            }
            screen = SCREEN_MEDIA_PLAYING;
        } else if (screen == SCREEN_WIFI_LIST &&
                   (action == ACTION_UP || action == ACTION_DOWN)) {
            unsigned total = wifi.list.count + 3;
            if (action == ACTION_UP)
                wifi.list.selected = wifi.list.selected == 0 ? total - 1 : wifi.list.selected - 1;
            else wifi.list.selected = (wifi.list.selected + 1) % total;
            draw_wifi_list(fb, &wifi);
        } else if (screen == SCREEN_WIFI_LIST && action == ACTION_OPEN) {
            if (wifi.list.selected < wifi.list.count) {
                if (wifi.list.networks[wifi.list.selected].secured) {
                    wifi.page = 0; wifi.cursor = 0; wifi.password_length = 0; wifi.password[0] = '\0';
                    screen = SCREEN_WIFI_KEYBOARD; draw_wifi_keyboard(fb, &wifi);
                } else {
                    draw_header(fb, "WIFI"); draw_centered(fb, 190, "CONNECTING", 5, color(fb, 245,177,52)); present(fb);
                    wifi.success = guide_wifi_connect(&wifi.list.networks[wifi.list.selected], "", log,
                                                      wifi.result, sizeof(wifi.result)) == 0;
                    screen = SCREEN_WIFI_RESULT; draw_wifi_result(fb, &wifi);
                }
            } else if (wifi.list.selected == wifi.list.count) wifi_scan_screen(fb, &wifi, log);
            else if (wifi.list.selected == wifi.list.count + 1) {
                wifi.success = guide_wifi_disconnect(log, wifi.result, sizeof(wifi.result)) == 0;
                screen = SCREEN_WIFI_RESULT; draw_wifi_result(fb, &wifi);
            } else {
                wifi.success = guide_wifi_forget(log, wifi.result, sizeof(wifi.result)) == 0;
                screen = SCREEN_WIFI_RESULT; draw_wifi_result(fb, &wifi);
            }
        } else if (screen == SCREEN_WIFI_KEYBOARD && action == ACTION_BACK) {
            memset(wifi.password, 0, sizeof(wifi.password)); wifi.password_length = 0;
            screen = SCREEN_WIFI_LIST; draw_wifi_list(fb, &wifi);
        } else if (screen == SCREEN_WIFI_KEYBOARD && action == ACTION_LEFT) {
            wifi.cursor = keyboard_move(wifi.cursor, -1, 0); draw_wifi_keyboard(fb, &wifi);
        } else if (screen == SCREEN_WIFI_KEYBOARD && action == ACTION_RIGHT) {
            wifi.cursor = keyboard_move(wifi.cursor, 1, 0); draw_wifi_keyboard(fb, &wifi);
        } else if (screen == SCREEN_WIFI_KEYBOARD && action == ACTION_UP) {
            wifi.cursor = keyboard_move(wifi.cursor, 0, -1); draw_wifi_keyboard(fb, &wifi);
        } else if (screen == SCREEN_WIFI_KEYBOARD && action == ACTION_DOWN) {
            wifi.cursor = keyboard_move(wifi.cursor, 0, 1); draw_wifi_keyboard(fb, &wifi);
        } else if (screen == SCREEN_WIFI_KEYBOARD && action == ACTION_SPACE) {
            if (wifi.password_length < GUIDE_WIFI_PASSWORD_MAX) {
                wifi.password[wifi.password_length++] = ' ';
                wifi.password[wifi.password_length] = '\0';
            }
            draw_wifi_keyboard(fb, &wifi);
        } else if (screen == SCREEN_WIFI_KEYBOARD && action == ACTION_OPEN) {
            wifi_keyboard_select(fb, &wifi, &screen, log);
        } else if (screen == SCREEN_WIFI_RESULT && action == ACTION_BACK) {
            screen = SCREEN_WIFI_LIST; draw_wifi_list(fb, &wifi);
        } else if (screen == SCREEN_WIKIPEDIA_HOME && action == ACTION_OPEN &&
                   guide_wikipedia_installed()) {
            if (!guide_wifi_link_up()) {
                snprintf(wiki.message, sizeof(wiki.message), "CONNECT WIFI FIRST");
                draw_wikipedia_home(fb, &wiki);
            } else {
                wiki.keyboard_page = 1; wiki.cursor = 0; wiki.query_length = 0;
                wiki.query[0] = '\0'; wiki.message[0] = '\0';
                screen = SCREEN_WIKIPEDIA_KEYBOARD; draw_wikipedia_keyboard(fb, &wiki);
            }
        } else if (screen == SCREEN_WIKIPEDIA_KEYBOARD && action == ACTION_BACK) {
            screen = SCREEN_WIKIPEDIA_HOME; draw_wikipedia_home(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_KEYBOARD && action == ACTION_LEFT) {
            wiki.cursor = keyboard_move(wiki.cursor, -1, 0);
            draw_wikipedia_keyboard(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_KEYBOARD && action == ACTION_RIGHT) {
            wiki.cursor = keyboard_move(wiki.cursor, 1, 0);
            draw_wikipedia_keyboard(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_KEYBOARD && action == ACTION_UP) {
            wiki.cursor = keyboard_move(wiki.cursor, 0, -1);
            draw_wikipedia_keyboard(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_KEYBOARD && action == ACTION_DOWN) {
            wiki.cursor = keyboard_move(wiki.cursor, 0, 1);
            draw_wikipedia_keyboard(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_KEYBOARD && action == ACTION_SPACE) {
            if (wiki.query_length < GUIDE_WIKI_QUERY_MAX) {
                wiki.query[wiki.query_length++] = ' ';
                wiki.query[wiki.query_length] = '\0';
            }
            draw_wikipedia_keyboard(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_KEYBOARD && action == ACTION_OPEN) {
            wikipedia_keyboard_select(fb, &wiki, &screen, log);
        } else if (screen == SCREEN_WIKIPEDIA_RESULTS &&
                   (action == ACTION_UP || action == ACTION_LEFT)) {
            if (wiki.result_count)
                wiki.selected_result = wiki.selected_result == 0 ?
                    wiki.result_count - 1 : wiki.selected_result - 1;
            draw_wikipedia_results(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_RESULTS &&
                   (action == ACTION_DOWN || action == ACTION_RIGHT)) {
            if (wiki.result_count)
                wiki.selected_result = (wiki.selected_result + 1) % wiki.result_count;
            draw_wikipedia_results(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_RESULTS && action == ACTION_OPEN &&
                   wiki.result_count) {
            draw_header(fb, "WIKIPEDIA");
            draw_centered(fb, 180, "LOADING ARTICLE", 5, color(fb, 245, 177, 52));
            draw_centered(fb, 270, "FULL PLAIN-TEXT EDITION", 2,
                          color(fb, 151, 220, 231)); present(fb);
            if (wikipedia_fetch_article(&wiki,
                    wiki.results[wiki.selected_result].title, log) == 0) {
                screen = SCREEN_WIKIPEDIA_ARTICLE; draw_wikipedia_article(fb, &wiki);
            } else draw_wikipedia_results(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_RESULTS && action == ACTION_BACK) {
            screen = SCREEN_WIKIPEDIA_KEYBOARD; draw_wikipedia_keyboard(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_ARTICLE &&
                   (action == ACTION_UP || action == ACTION_LEFT)) {
            if (wiki.page) --wiki.page;
            draw_wikipedia_article(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_ARTICLE &&
                   (action == ACTION_DOWN || action == ACTION_RIGHT)) {
            if (wiki.page + 1 < wiki.known_pages) ++wiki.page;
            draw_wikipedia_article(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_ARTICLE && action == ACTION_BACK) {
            screen = SCREEN_WIKIPEDIA_RESULTS; draw_wikipedia_results(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_ARTICLE && action == ACTION_OPEN &&
                   wiki.link_count) {
            wiki.selected_link = wikipedia_first_link_on_page(&wiki);
            screen = SCREEN_WIKIPEDIA_LINKS;
            draw_wikipedia_links(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_LINKS && action == ACTION_UP) {
            wiki.selected_link = wiki.selected_link == 0 ?
                wiki.link_count - 1 : wiki.selected_link - 1;
            draw_wikipedia_links(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_LINKS && action == ACTION_DOWN) {
            wiki.selected_link = (wiki.selected_link + 1) % wiki.link_count;
            draw_wikipedia_links(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_LINKS && action == ACTION_LEFT) {
            wiki.selected_link = wiki.selected_link < 7 ? 0 : wiki.selected_link - 7;
            draw_wikipedia_links(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_LINKS && action == ACTION_RIGHT) {
            wiki.selected_link = wiki.selected_link + 7 >= wiki.link_count ?
                wiki.link_count - 1 : wiki.selected_link + 7;
            draw_wikipedia_links(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_LINKS && action == ACTION_OPEN) {
            char requested[301];
            snprintf(requested, sizeof(requested), "%s", wiki.links[wiki.selected_link].title);
            draw_header(fb, "WIKIPEDIA");
            draw_centered(fb, 180, "OPENING LINK", 5, color(fb, 245, 177, 52));
            present(fb);
            if (wikipedia_fetch_article(&wiki, requested, log) == 0) {
                screen = SCREEN_WIKIPEDIA_ARTICLE; draw_wikipedia_article(fb, &wiki);
            } else draw_wikipedia_links(fb, &wiki);
        } else if (screen == SCREEN_WIKIPEDIA_LINKS && action == ACTION_BACK) {
            screen = SCREEN_WIKIPEDIA_ARTICLE; draw_wikipedia_article(fb, &wiki);
        } else if (screen == SCREEN_DEVELOPER_LINK && action == ACTION_OPEN) {
            int active = developer_link_active(log);
            if (!guide_developer_link_installed()) {
                snprintf(developer_message, sizeof(developer_message), "INSTALL FROM CARTRIDGE");
            } else if (active) {
                snprintf(developer_message, sizeof(developer_message),
                         developer_link_control("stop", log) == 0 ? "LINK DISABLED" : "COULD NOT STOP LINK");
            } else if (!guide_wifi_link_up()) {
                snprintf(developer_message, sizeof(developer_message), "CONNECT WIFI FIRST");
            } else {
                snprintf(developer_message, sizeof(developer_message),
                         developer_link_control("start", log) == 0 ? "PHYSICALLY ENABLED" : "LINK START FAILED");
            }
            draw_developer_link(fb, log, developer_message);
        } else if (screen == SCREEN_CARTRIDGE_LIST && catalog.state == GUIDE_CARTRIDGE_READY &&
                   (action == ACTION_UP || action == ACTION_DOWN ||
                    action == ACTION_LEFT || action == ACTION_RIGHT)) {
            if (action == ACTION_UP || action == ACTION_LEFT)
                catalog.selected = catalog.selected == 0 ? catalog.count - 1 : catalog.selected - 1;
            else catalog.selected = (catalog.selected + 1) % catalog.count;
            draw_cartridge_list(fb, &catalog);
        } else if (screen == SCREEN_CARTRIDGE_LIST && action == ACTION_OPEN) {
            if (catalog.state == GUIDE_CARTRIDGE_READY) {
                (void)guide_cartridge_verify(&catalog, log);
                screen = SCREEN_CARTRIDGE_DETAIL;
                draw_cartridge_detail(fb, &catalog);
            } else {
                guide_cartridge_scan(&catalog, log);
                draw_cartridge_list(fb, &catalog);
            }
        } else if (screen == SCREEN_CARTRIDGE_DETAIL && action == ACTION_BACK) {
            screen = SCREEN_CARTRIDGE_LIST;
            draw_cartridge_list(fb, &catalog);
        } else if (screen == SCREEN_CARTRIDGE_DETAIL && action == ACTION_OPEN &&
                   catalog.state == GUIDE_CARTRIDGE_READY &&
                   (guide_wifi_install_supported(&catalog.items[catalog.selected]) ||
                    guide_developer_link_install_supported(&catalog.items[catalog.selected]) ||
                    guide_wikipedia_install_supported(&catalog.items[catalog.selected]))) {
            screen = SCREEN_INSTALL_CONFIRM;
            draw_install_confirm(fb, &catalog.items[catalog.selected]);
        } else if (screen == SCREEN_INSTALL_CONFIRM && action == ACTION_BACK) {
            screen = SCREEN_CARTRIDGE_DETAIL;
            draw_cartridge_detail(fb, &catalog);
        } else if (screen == SCREEN_INSTALL_CONFIRM && action == ACTION_OPEN) {
            draw_header(fb, "INSTALL");
            draw_centered(fb, 190,
                          guide_developer_link_install_supported(&catalog.items[catalog.selected]) ?
                          "INSTALLING LINK" :
                          guide_wikipedia_install_supported(&catalog.items[catalog.selected]) ?
                          "INSTALLING WIKIPEDIA" : "INSTALLING WIFI", 4,
                          color(fb, 244, 241, 228));
            draw_centered(fb, 272, "VERIFYING EVERY FILE", 3, color(fb, 245, 177, 52));
            draw_centered(fb, 332, "DO NOT POWER OFF", 2, color(fb, 151, 220, 231));
            present(fb);
            if (guide_developer_link_install_supported(&catalog.items[catalog.selected]))
                install_success = guide_developer_link_install(&catalog.items[catalog.selected], log,
                                                               install_message, sizeof(install_message)) == 0;
            else if (guide_wikipedia_install_supported(&catalog.items[catalog.selected]))
                install_success = guide_wikipedia_install(&catalog.items[catalog.selected], log,
                                                          install_message, sizeof(install_message)) == 0;
            else
                install_success = guide_wifi_install(&catalog.items[catalog.selected], log,
                                                     install_message, sizeof(install_message)) == 0;
            screen = SCREEN_INSTALL_RESULT;
            draw_install_result(fb, install_message, install_success);
        } else if (screen == SCREEN_INSTALL_RESULT && action == ACTION_BACK) {
            screen = SCREEN_CARTRIDGE_DETAIL;
            draw_cartridge_detail(fb, &catalog);
        } else if (action == ACTION_BACK) {
            if (screen == SCREEN_CARTRIDGE_LIST) guide_cartridge_release(&catalog, log);
            screen = SCREEN_MENU;
            draw_menu(fb, selected);
        }
        else if (screen == SCREEN_INPUT) draw_input_test(fb, event.type, event.code, event.value);
    }
}

int main(void)
{
    struct framebuffer fb;
    struct timespec welcome_time = {3, 0};
    FILE *log, *marker;
    restore_clock_floor();
    (void)mount("proc", "/proc", "proc", 0, NULL);
    (void)mount("sysfs", "/sys", "sysfs", 0, NULL);
    marker = fopen("/hello-world-init-ran", "w");
    if (marker) { fprintf(marker, "PID1_REACHED pid=%ld\nGUIDE_SHELL_STARTED=1\n", (long)getpid()); fclose(marker); }
    log = fopen("/guide-framebuffer-diagnostics.txt", "w");
    if (!log) log = stderr;
    fprintf(log, "GUIDEOS INTERACTIVE SHELL BOOT DIAGNOSTICS\n");
    guide_wifi_start_installed(log);
    log_wifi_diagnostics(log);
    fflush(log);
    guide_wifi_autoconnect();
    if (open_framebuffer(&fb, log) != 0) {
        if (getpid() == 1) for (;;) sleep(3600);
        return 1;
    }
    draw_welcome(&fb, log); nanosleep(&welcome_time, NULL); run_shell(&fb, log);
    close_framebuffer(&fb);
    if (log != stderr) fclose(log);
    return 0;
}
