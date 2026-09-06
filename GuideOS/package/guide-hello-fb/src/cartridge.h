// SPDX-License-Identifier: AGPL-3.0-or-later

#ifndef GUIDE_CARTRIDGE_H
#define GUIDE_CARTRIDGE_H

#include <stdio.h>

#define GUIDE_CARTRIDGE_LIMIT 8

enum guide_cartridge_state {
    GUIDE_CARTRIDGE_NO_CARD,
    GUIDE_CARTRIDGE_MOUNT_ERROR,
    GUIDE_CARTRIDGE_EMPTY,
    GUIDE_CARTRIDGE_INVALID,
    GUIDE_CARTRIDGE_READY
};

enum guide_cartridge_verification {
    GUIDE_CARTRIDGE_UNCHECKED,
    GUIDE_CARTRIDGE_VERIFIED,
    GUIDE_CARTRIDGE_VERIFY_FAILED,
    GUIDE_CARTRIDGE_VERIFY_UNAVAILABLE
};

struct guide_cartridge {
    char id[65];
    char name[23];
    char version[17];
    char kind[17];
    char summary[45];
    char file[97];
    char sha256[65];
    char capability[33];
    char action[49];
    unsigned long long bytes;
    unsigned capability_count;
    enum guide_cartridge_verification verification;
};

struct guide_cartridge_catalog {
    enum guide_cartridge_state state;
    int mounted;
    unsigned count;
    unsigned selected;
    unsigned invalid_count;
    char detail[53];
    struct guide_cartridge items[GUIDE_CARTRIDGE_LIMIT];
};

void guide_cartridge_release(struct guide_cartridge_catalog *catalog, FILE *log);
void guide_cartridge_scan(struct guide_cartridge_catalog *catalog, FILE *log);
int guide_cartridge_verify(struct guide_cartridge_catalog *catalog, FILE *log);
int guide_sha256_file(const char *path, char output[65]);

#endif
