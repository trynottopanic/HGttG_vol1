// SPDX-License-Identifier: AGPL-3.0-or-later

#ifndef GUIDE_PAYLOAD_H
#define GUIDE_PAYLOAD_H

#include <stdio.h>

enum guide_payload_state {
    GUIDE_PAYLOAD_NO_CARD,
    GUIDE_PAYLOAD_MOUNT_ERROR,
    GUIDE_PAYLOAD_NO_MANIFEST,
    GUIDE_PAYLOAD_INVALID,
    GUIDE_PAYLOAD_READY
};

struct guide_payload_status {
    enum guide_payload_state state;
    int mounted;
    char name[23];
    char type[17];
    char summary[45];
    char detail[53];
};

void guide_payload_release(struct guide_payload_status *status, FILE *log);
void guide_payload_scan(struct guide_payload_status *status, FILE *log);

#endif
