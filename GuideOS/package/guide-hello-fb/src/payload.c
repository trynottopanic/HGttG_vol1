// SPDX-License-Identifier: AGPL-3.0-or-later

#include "payload.h"

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <unistd.h>

#define PAYLOAD_MOUNT "/media/guide-card"
#define PAYLOAD_MANIFEST PAYLOAD_MOUNT "/GUIDE/PAYLOAD.GDE"
#define MANIFEST_LIMIT 4096

static void display_text(char *destination, size_t capacity, const char *source)
{
    size_t index;
    if (capacity == 0)
        return;
    for (index = 0; index + 1 < capacity && source[index]; ++index) {
        unsigned char value = (unsigned char)source[index];
        if (value >= 'a' && value <= 'z')
            value = (unsigned char)toupper(value);
        if (!(value == ' ' || value == '-' || value == '.' || value == ':' ||
              (value >= '0' && value <= '9') ||
              (value >= 'A' && value <= 'Z')))
            value = ' ';
        destination[index] = (char)value;
    }
    destination[index] = '\0';
}

static int assign_field(char *destination, size_t capacity, const char *line,
                        const char *field)
{
    size_t length = strlen(field);
    if (strncmp(line, field, length) != 0 || line[length] != '=')
        return 0;
    if (line[length + 1] == '\0')
        return -1;
    display_text(destination, capacity, line + length + 1);
    return 1;
}

static int parse_manifest(struct guide_payload_status *status, FILE *log)
{
    char content[MANIFEST_LIMIT + 1];
    char *line, *next;
    struct stat info;
    ssize_t count;
    int fd, have_name = 0, have_type = 0;

    fd = open(PAYLOAD_MANIFEST, O_RDONLY | O_NOFOLLOW);
    if (fd < 0) {
        status->state = errno == ENOENT ? GUIDE_PAYLOAD_NO_MANIFEST :
                                         GUIDE_PAYLOAD_INVALID;
        display_text(status->detail, sizeof(status->detail),
                     errno == ENOENT ? "GUIDE PAYLOAD.GDE NOT FOUND" :
                                       "MANIFEST COULD NOT BE OPENED");
        return -1;
    }
    if (fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) || info.st_size <= 0 ||
        info.st_size > MANIFEST_LIMIT) {
        close(fd);
        status->state = GUIDE_PAYLOAD_INVALID;
        display_text(status->detail, sizeof(status->detail),
                     "MANIFEST MUST BE A SMALL REGULAR FILE");
        return -1;
    }
    count = read(fd, content, sizeof(content) - 1);
    close(fd);
    if (count != info.st_size) {
        status->state = GUIDE_PAYLOAD_INVALID;
        display_text(status->detail, sizeof(status->detail),
                     "MANIFEST READ WAS INCOMPLETE");
        return -1;
    }
    content[count] = '\0';
    for (count = 0; content[count]; ++count) {
        unsigned char value = (unsigned char)content[count];
        if (value != '\n' && value != '\r' && value != '\t' &&
            (value < 32 || value > 126)) {
            status->state = GUIDE_PAYLOAD_INVALID;
            display_text(status->detail, sizeof(status->detail),
                         "MANIFEST CONTAINS NON-TEXT DATA");
            return -1;
        }
    }

    line = content;
    next = strchr(line, '\n');
    if (next)
        *next++ = '\0';
    if (strchr(line, '\r'))
        *strchr(line, '\r') = '\0';
    if (strcmp(line, "GUIDE-PAYLOAD-0") != 0) {
        status->state = GUIDE_PAYLOAD_INVALID;
        display_text(status->detail, sizeof(status->detail),
                     "UNSUPPORTED PAYLOAD VERSION");
        return -1;
    }
    while (next && *next) {
        int result;
        line = next;
        next = strchr(line, '\n');
        if (next)
            *next++ = '\0';
        if (strchr(line, '\r'))
            *strchr(line, '\r') = '\0';
        if (*line == '\0' || *line == '#')
            continue;
        result = assign_field(status->name, sizeof(status->name), line, "NAME");
        if (result != 0) {
            if (result < 0) goto invalid_field;
            have_name = 1;
            continue;
        }
        result = assign_field(status->type, sizeof(status->type), line, "TYPE");
        if (result != 0) {
            if (result < 0) goto invalid_field;
            have_type = 1;
            continue;
        }
        result = assign_field(status->summary, sizeof(status->summary), line,
                              "SUMMARY");
        if (result < 0) goto invalid_field;
    }
    if (!have_name || !have_type)
        goto invalid_field;
    status->state = GUIDE_PAYLOAD_READY;
    display_text(status->detail, sizeof(status->detail),
                 "RECOGNIZED READ-ONLY PAYLOAD");
    fprintf(log, "payload ready name=%s type=%s\n", status->name, status->type);
    fflush(log);
    return 0;

invalid_field:
    status->state = GUIDE_PAYLOAD_INVALID;
    display_text(status->detail, sizeof(status->detail),
                 "NAME AND TYPE ARE REQUIRED");
    return -1;
}

void guide_payload_release(struct guide_payload_status *status, FILE *log)
{
    if (!status->mounted)
        return;
    if (umount(PAYLOAD_MOUNT) == 0) {
        status->mounted = 0;
        fprintf(log, "external payload card unmounted\n");
    } else {
        fprintf(log, "external payload unmount failed: %s\n", strerror(errno));
    }
    fflush(log);
}

void guide_payload_scan(struct guide_payload_status *status, FILE *log)
{
    static const char *devices[] = {"/dev/mmcblk1p1", "/dev/mmcblk1"};
    static const char *filesystems[] = {"vfat", "ext4"};
    size_t device, filesystem;

    guide_payload_release(status, log);
    if (status->mounted) {
        status->state = GUIDE_PAYLOAD_MOUNT_ERROR;
        display_text(status->detail, sizeof(status->detail),
                     "PREVIOUS CARD COULD NOT BE RELEASED");
        return;
    }
    memset(status, 0, sizeof(*status));
    status->state = GUIDE_PAYLOAD_NO_CARD;
    display_text(status->detail, sizeof(status->detail), "NO EXTERNAL CARD FOUND");
    (void)mkdir("/media", 0755);
    (void)mkdir(PAYLOAD_MOUNT, 0755);

    for (device = 0; device < sizeof(devices) / sizeof(devices[0]); ++device) {
        if (access(devices[device], F_OK) != 0)
            continue;
        status->state = GUIDE_PAYLOAD_MOUNT_ERROR;
        display_text(status->detail, sizeof(status->detail),
                     "CARD FOUND BUT MOUNT FAILED");
        for (filesystem = 0;
             filesystem < sizeof(filesystems) / sizeof(filesystems[0]);
             ++filesystem) {
            unsigned long flags = MS_RDONLY | MS_NODEV | MS_NOSUID | MS_NOEXEC;
            if (mount(devices[device], PAYLOAD_MOUNT, filesystems[filesystem],
                      flags, NULL) == 0) {
                status->mounted = 1;
                fprintf(log, "external card=%s filesystem=%s flags=ro,nodev,nosuid,noexec\n",
                        devices[device], filesystems[filesystem]);
                fflush(log);
                (void)parse_manifest(status, log);
                return;
            }
        }
        fprintf(log, "external card mount failed device=%s error=%s\n",
                devices[device], strerror(errno));
        fflush(log);
        return;
    }
}
