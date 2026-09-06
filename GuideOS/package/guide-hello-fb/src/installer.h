// SPDX-License-Identifier: AGPL-3.0-or-later

#ifndef GUIDE_INSTALLER_H
#define GUIDE_INSTALLER_H

#include <stddef.h>
#include <stdio.h>

#include "cartridge.h"

int guide_wifi_install_supported(const struct guide_cartridge *item);
int guide_wifi_install(const struct guide_cartridge *item, FILE *log,
                       char *message, size_t message_size);
void guide_wifi_start_installed(FILE *log);
int guide_developer_link_install_supported(const struct guide_cartridge *item);
int guide_developer_link_install(const struct guide_cartridge *item, FILE *log,
                                 char *message, size_t message_size);
int guide_developer_link_installed(void);
int guide_wikipedia_install_supported(const struct guide_cartridge *item);
int guide_wikipedia_install(const struct guide_cartridge *item, FILE *log,
                            char *message, size_t message_size);
int guide_wikipedia_installed(void);

#endif
