################################################################################
#
# guide-supervisor
#
################################################################################

GUIDE_SUPERVISOR_SITE = $(BR2_EXTERNAL_GUIDE_OS_PATH)/package/guide-supervisor/src
GUIDE_SUPERVISOR_SITE_METHOD = local
GUIDE_SUPERVISOR_LICENSE = AGPL-3.0-or-later

define GUIDE_SUPERVISOR_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) -static -Wall -Wextra -Werror \
		-o $(@D)/guide-supervisor $(@D)/guide-supervisor.c
endef

define GUIDE_SUPERVISOR_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/guide-supervisor \
		$(TARGET_DIR)/usr/sbin/guide-supervisor
endef

$(eval $(generic-package))
