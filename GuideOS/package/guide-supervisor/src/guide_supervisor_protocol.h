// SPDX-License-Identifier: AGPL-3.0-or-later
#ifndef GUIDE_SUPERVISOR_PROTOCOL_H
#define GUIDE_SUPERVISOR_PROTOCOL_H

#include <stdint.h>

#define GUIDE_SUPERVISOR_FD_ENV "GUIDE_SUPERVISOR_FD"
#define GUIDE_SUPERVISOR_MAGIC 0x47535631u
#define GUIDE_SUPERVISOR_VERSION 1u
#define GUIDE_SUPERVISOR_POWER_EXIT 32

enum guide_supervisor_command {
    GUIDE_SUPERVISOR_RUN = 1,
    GUIDE_SUPERVISOR_SHUTDOWN = 2
};

enum guide_supervisor_application {
    GUIDE_APPLICATION_EMULATOR = 1,
    GUIDE_APPLICATION_DOOM = 2,
    GUIDE_APPLICATION_WEB_BROWSER = 3,
    GUIDE_APPLICATION_WIKIPEDIA = 4
};

enum guide_priority_class {
    GUIDE_PRIORITY_SAFETY = 0,
    GUIDE_PRIORITY_FOREGROUND = 1,
    GUIDE_PRIORITY_COMMUNICATION = 2,
    GUIDE_PRIORITY_BACKGROUND = 3,
    GUIDE_PRIORITY_OPPORTUNISTIC = 4
};

enum guide_supervisor_result {
    GUIDE_RESULT_COMPLETE = 0,
    GUIDE_RESULT_POWER_REQUESTED = 1,
    GUIDE_RESULT_FAILED = 2,
    GUIDE_RESULT_REJECTED = 3,
    GUIDE_RESULT_SHUTTING_DOWN = 4
};

struct guide_supervisor_request {
    uint32_t magic;
    uint32_t version;
    uint32_t command;
    uint32_t application;
    uint32_t priority;
    char argument0[64];
    char argument1[768];
};

struct guide_supervisor_response {
    uint32_t magic;
    uint32_t version;
    uint32_t result;
    int32_t wait_status;
    int32_t error_number;
    char message[128];
};

#endif
