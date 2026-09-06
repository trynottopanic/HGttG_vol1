// SPDX-License-Identifier: AGPL-3.0-or-later

#include "cartridge.h"

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#define CARD_MOUNT "/media/guide-card"
#define CARTRIDGE_DIRECTORY CARD_MOUNT "/GUIDE/CARTRIDGES"
#define INDEX_LIMIT 4096
#define CARTRIDGE_BYTES_LIMIT (128ULL * 1024ULL * 1024ULL * 1024ULL)

static void display_text(char *destination, size_t capacity, const char *source)
{
    size_t index;
    if (capacity == 0) return;
    for (index = 0; index + 1 < capacity && source[index]; ++index) {
        unsigned char value = (unsigned char)source[index];
        if (value >= 'a' && value <= 'z') value = (unsigned char)toupper(value);
        if (!(value == ' ' || value == '-' || value == '.' || value == ':' ||
              (value >= '0' && value <= '9') ||
              (value >= 'A' && value <= 'Z'))) value = ' ';
        destination[index] = (char)value;
    }
    destination[index] = '\0';
}

static int safe_token(const char *text, size_t maximum)
{
    size_t index, length = strlen(text);
    if (length == 0 || length > maximum || text[0] == '.') return 0;
    for (index = 0; index < length; ++index)
        if (!(isalnum((unsigned char)text[index]) || text[index] == '.' ||
              text[index] == '-' || text[index] == '_')) return 0;
    return 1;
}

static int valid_hash(const char *text)
{
    size_t index;
    if (strlen(text) != 64) return 0;
    for (index = 0; index < 64; ++index)
        if (!isxdigit((unsigned char)text[index])) return 0;
    return 1;
}

static int ends_with(const char *text, const char *suffix)
{
    size_t text_length = strlen(text), suffix_length = strlen(suffix);
    return text_length >= suffix_length &&
           strcmp(text + text_length - suffix_length, suffix) == 0;
}

static int copy_raw(char *destination, size_t capacity, const char *source)
{
    size_t length = strlen(source);
    if (length == 0 || length >= capacity) return -1;
    memcpy(destination, source, length + 1);
    return 0;
}

static int parse_index(const char *path, struct guide_cartridge *item, FILE *log)
{
    char content[INDEX_LIMIT + 1], *line, *next;
    struct stat info;
    ssize_t count;
    int fd, first = 1, have_id = 0, have_name = 0, have_version = 0;
    int have_kind = 0, have_file = 0, have_bytes = 0, have_hash = 0;

    memset(item, 0, sizeof(*item));
    fd = open(path, O_RDONLY | O_NOFOLLOW);
    if (fd < 0) return -1;
    if (fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) ||
        info.st_size <= 0 || info.st_size > INDEX_LIMIT) {
        close(fd); return -1;
    }
    count = read(fd, content, sizeof(content) - 1);
    close(fd);
    if (count != info.st_size) return -1;
    content[count] = '\0';
    for (count = 0; content[count]; ++count) {
        unsigned char value = (unsigned char)content[count];
        if (value != '\n' && value != '\r' && value != '\t' &&
            (value < 32 || value > 126)) return -1;
    }

    line = content;
    while (line && *line) {
        char *equals;
        next = strchr(line, '\n');
        if (next) *next++ = '\0';
        equals = strchr(line, '\r');
        if (equals) *equals = '\0';
        if (first) {
            first = 0;
            if (strcmp(line, "GUIDE-CARTRIDGE-INDEX-1") != 0) return -1;
            line = next; continue;
        }
        if (*line == '\0' || *line == '#') { line = next; continue; }
        equals = strchr(line, '=');
        if (!equals || equals == line) return -1;
        *equals++ = '\0';
        if (*equals == '\0' && strcmp(line, "SUMMARY") != 0) return -1;
        if (strcmp(line, "ID") == 0) {
            if (have_id || copy_raw(item->id, sizeof(item->id), equals) != 0) return -1;
            have_id = 1;
        } else if (strcmp(line, "NAME") == 0) {
            if (have_name) return -1;
            display_text(item->name, sizeof(item->name), equals); have_name = 1;
        } else if (strcmp(line, "VERSION") == 0) {
            if (have_version || copy_raw(item->version, sizeof(item->version), equals) != 0) return -1;
            have_version = 1;
        } else if (strcmp(line, "KIND") == 0) {
            if (have_kind) return -1;
            display_text(item->kind, sizeof(item->kind), equals); have_kind = 1;
        } else if (strcmp(line, "SUMMARY") == 0) {
            display_text(item->summary, sizeof(item->summary), equals);
        } else if (strcmp(line, "FILE") == 0) {
            if (have_file || copy_raw(item->file, sizeof(item->file), equals) != 0) return -1;
            have_file = 1;
        } else if (strcmp(line, "BYTES") == 0) {
            char *end;
            unsigned long long value;
            if (have_bytes || *equals == '-') return -1;
            errno = 0; value = strtoull(equals, &end, 10);
            if (errno || *end != '\0') return -1;
            item->bytes = value; have_bytes = 1;
        } else if (strcmp(line, "SHA256") == 0) {
            size_t index;
            if (have_hash || copy_raw(item->sha256, sizeof(item->sha256), equals) != 0) return -1;
            for (index = 0; item->sha256[index]; ++index)
                item->sha256[index] = (char)tolower((unsigned char)item->sha256[index]);
            have_hash = 1;
        } else if (strcmp(line, "CAPABILITY") == 0) {
            if (item->capability_count == 0)
                display_text(item->capability, sizeof(item->capability), equals);
            ++item->capability_count;
        } else if (strcmp(line, "ACTION") == 0) {
            if (item->action[0] || copy_raw(item->action, sizeof(item->action), equals) != 0) return -1;
        } else return -1;
        line = next;
    }
    if (!have_id || !have_name || item->name[0] == '\0' || !have_version || !have_kind || !have_file ||
        !have_bytes || !have_hash || !safe_token(item->id, 64) ||
        !safe_token(item->version, 16) || !safe_token(item->file, 96) ||
        !ends_with(item->file, ".guide") || !valid_hash(item->sha256) ||
        item->bytes > CARTRIDGE_BYTES_LIMIT ||
        (item->action[0] && !safe_token(item->action, 48))) return -1;
    item->verification = GUIDE_CARTRIDGE_UNCHECKED;
    fprintf(log, "cartridge index id=%s version=%s file=%s action=%s\n",
            item->id, item->version, item->file,
            item->action[0] ? item->action : "none");
    return 0;
}

static int compare_cartridges(const void *left, const void *right)
{
    const struct guide_cartridge *a = left, *b = right;
    int result = strcmp(a->name, b->name);
    return result ? result : strcmp(a->id, b->id);
}

void guide_cartridge_release(struct guide_cartridge_catalog *catalog, FILE *log)
{
    if (!catalog->mounted) return;
    if (umount(CARD_MOUNT) == 0) {
        catalog->mounted = 0;
        fprintf(log, "external cartridge card unmounted\n");
    } else fprintf(log, "external cartridge unmount failed: %s\n", strerror(errno));
    fflush(log);
}

void guide_cartridge_scan(struct guide_cartridge_catalog *catalog, FILE *log)
{
    static const char *devices[] = {"/dev/mmcblk1p1", "/dev/mmcblk1"};
    static const char *filesystems[] = {"vfat", "ext4"};
    DIR *directory;
    struct dirent *entry;
    size_t device, filesystem;

    guide_cartridge_release(catalog, log);
    if (catalog->mounted) {
        catalog->state = GUIDE_CARTRIDGE_MOUNT_ERROR;
        display_text(catalog->detail, sizeof(catalog->detail), "PREVIOUS CARD COULD NOT BE RELEASED");
        return;
    }
    memset(catalog, 0, sizeof(*catalog));
    catalog->state = GUIDE_CARTRIDGE_NO_CARD;
    display_text(catalog->detail, sizeof(catalog->detail), "NO EXTERNAL CARD FOUND");
    (void)mkdir("/media", 0755); (void)mkdir(CARD_MOUNT, 0755);
    for (device = 0; device < sizeof(devices) / sizeof(devices[0]); ++device) {
        if (access(devices[device], F_OK) != 0) continue;
        catalog->state = GUIDE_CARTRIDGE_MOUNT_ERROR;
        display_text(catalog->detail, sizeof(catalog->detail), "CARD FOUND BUT MOUNT FAILED");
        for (filesystem = 0; filesystem < sizeof(filesystems) / sizeof(filesystems[0]); ++filesystem) {
            unsigned long flags = MS_RDONLY | MS_NODEV | MS_NOSUID | MS_NOEXEC;
            if (mount(devices[device], CARD_MOUNT, filesystems[filesystem], flags, NULL) == 0) {
                catalog->mounted = 1;
                fprintf(log, "cartridge card=%s filesystem=%s flags=ro,nodev,nosuid,noexec\n",
                        devices[device], filesystems[filesystem]);
                goto mounted;
            }
        }
        fprintf(log, "cartridge card mount failed device=%s error=%s\n",
                devices[device], strerror(errno)); fflush(log); return;
    }
    return;

mounted:
    directory = opendir(CARTRIDGE_DIRECTORY);
    if (!directory) {
        catalog->state = GUIDE_CARTRIDGE_EMPTY;
        display_text(catalog->detail, sizeof(catalog->detail), "NO RECOGNIZED GUIDE CARTRIDGES");
        return;
    }
    while ((entry = readdir(directory)) != NULL) {
        char path[PATH_MAX];
        if (!ends_with(entry->d_name, ".gde")) continue;
        if (catalog->count >= GUIDE_CARTRIDGE_LIMIT) { ++catalog->invalid_count; continue; }
        if (snprintf(path, sizeof(path), "%s/%s", CARTRIDGE_DIRECTORY, entry->d_name) >= (int)sizeof(path) ||
            parse_index(path, &catalog->items[catalog->count], log) != 0) {
            ++catalog->invalid_count; continue;
        }
        ++catalog->count;
    }
    closedir(directory);
    if (catalog->count) {
        qsort(catalog->items, catalog->count, sizeof(catalog->items[0]), compare_cartridges);
        catalog->state = GUIDE_CARTRIDGE_READY;
        display_text(catalog->detail, sizeof(catalog->detail), "SELECT A CARTRIDGE");
    } else {
        catalog->state = catalog->invalid_count ? GUIDE_CARTRIDGE_INVALID : GUIDE_CARTRIDGE_EMPTY;
        display_text(catalog->detail, sizeof(catalog->detail),
                     catalog->invalid_count ? "CARTRIDGE FORMAT NOT RECOGNIZED" :
                     "NO RECOGNIZED GUIDE CARTRIDGES");
    }
    fflush(log);
}

int guide_sha256_file(const char *path, char output[65])
{
    int pipefd[2], status;
    ssize_t count, total = 0;
    pid_t child;
    if (pipe(pipefd) != 0) return -1;
    child = fork();
    if (child < 0) { close(pipefd[0]); close(pipefd[1]); return -1; }
    if (child == 0) {
        close(pipefd[0]);
        if (dup2(pipefd[1], STDOUT_FILENO) < 0) _exit(126);
        close(pipefd[1]);
        execl("/usr/bin/sha256sum", "sha256sum", path, (char *)NULL);
        execl("/bin/sha256sum", "sha256sum", path, (char *)NULL);
        _exit(127);
    }
    close(pipefd[1]);
    while (total < 64 && (count = read(pipefd[0], output + total, 64 - (size_t)total)) > 0)
        total += count;
    close(pipefd[0]);
    if (waitpid(child, &status, 0) < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0 || total != 64)
        return -1;
    output[64] = '\0';
    return valid_hash(output) ? 0 : -1;
}

int guide_cartridge_verify(struct guide_cartridge_catalog *catalog, FILE *log)
{
    struct guide_cartridge *item;
    struct stat info;
    char path[PATH_MAX], actual[65];
    if (catalog->state != GUIDE_CARTRIDGE_READY || catalog->selected >= catalog->count) return -1;
    item = &catalog->items[catalog->selected];
    if (snprintf(path, sizeof(path), "%s/%s", CARTRIDGE_DIRECTORY, item->file) >= (int)sizeof(path) ||
        lstat(path, &info) != 0 || !S_ISREG(info.st_mode) ||
        (unsigned long long)info.st_size != item->bytes) {
        item->verification = GUIDE_CARTRIDGE_VERIFY_FAILED;
        fprintf(log, "cartridge verify size/path failed id=%s error=%s\n", item->id, strerror(errno));
        fflush(log); return -1;
    }
    if (guide_sha256_file(path, actual) != 0) {
        item->verification = GUIDE_CARTRIDGE_VERIFY_UNAVAILABLE;
        fprintf(log, "cartridge sha256 tool unavailable id=%s\n", item->id);
        fflush(log); return -1;
    }
    if (strcmp(actual, item->sha256) != 0) {
        item->verification = GUIDE_CARTRIDGE_VERIFY_FAILED;
        fprintf(log, "cartridge hash mismatch id=%s expected=%s actual=%s\n",
                item->id, item->sha256, actual);
        fflush(log); return -1;
    }
    item->verification = GUIDE_CARTRIDGE_VERIFIED;
    fprintf(log, "cartridge verified id=%s sha256=%s unsigned=1\n", item->id, actual);
    fflush(log); return 0;
}
