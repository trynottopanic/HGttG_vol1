// SPDX-License-Identifier: AGPL-3.0-or-later
#ifndef GUIDE_WIFI_H
#define GUIDE_WIFI_H

#include <stddef.h>
#include <stdio.h>

#define GUIDE_WIFI_MAX_NETWORKS 16
#define GUIDE_WIFI_SSID_MAX 32
#define GUIDE_WIFI_PASSWORD_MAX 63

struct guide_wifi_network {
    char ssid[GUIDE_WIFI_SSID_MAX + 1];
    int signal_dbm;
    int secured;
};

struct guide_wifi_list {
    struct guide_wifi_network networks[GUIDE_WIFI_MAX_NETWORKS];
    unsigned count;
    unsigned selected;
    char message[80];
};

int guide_wifi_available(void);
int guide_wifi_link_up(void);
void guide_wifi_autoconnect(void);
int guide_wifi_scan(struct guide_wifi_list *list, FILE *log);
int guide_wifi_connect(const struct guide_wifi_network *network,
                       const char *password, FILE *log,
                       char *message, size_t message_size);
int guide_wifi_disconnect(FILE *log, char *message, size_t message_size);
int guide_wifi_forget(FILE *log, char *message, size_t message_size);
int guide_wifi_status(char *ssid, size_t ssid_size,
                      char *address, size_t address_size);

#endif
