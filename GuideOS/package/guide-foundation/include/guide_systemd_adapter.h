#ifndef GUIDE_SYSTEMD_ADAPTER_H
#define GUIDE_SYSTEMD_ADAPTER_H

#include <stdbool.h>
#include <stdint.h>
#include <systemd/sd-bus.h>

#define GUIDE_SYSTEMD_VALUE_MAX 256u

struct guide_systemd_observation {
    uint32_t main_pid, main_uid, job_id;
    uint64_t main_started;
    int32_t main_status;
    char invocation_id[33];
    char control_group[GUIDE_SYSTEMD_VALUE_MAX];
    char active_state[32];
    char sub_state[32];
};

int guide_systemd_connect(sd_bus **bus);
int guide_systemd_start_probe(sd_bus *bus, const char *unit, const char *executable,
                              const char *user,
                              uint64_t memory_high, uint64_t memory_max,
                              uint64_t tasks_max);
int guide_systemd_start_application(sd_bus *bus,const char *unit,uint64_t code,int health);
int guide_systemd_observe(sd_bus *bus, const char *unit,
                          struct guide_systemd_observation *observation);
int guide_systemd_reference(sd_bus *bus,const char *unit,int retain);
int guide_systemd_stop(sd_bus *bus, const char *unit);
int guide_systemd_reset_failed(sd_bus *bus, const char *unit);

#endif
