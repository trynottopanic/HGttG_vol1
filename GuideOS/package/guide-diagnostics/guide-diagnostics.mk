################################################################################
#
# guide-diagnostics
#
################################################################################

GUIDE_DIAGNOSTICS_SITE = $(BR2_EXTERNAL_GUIDE_OS_PATH)/apps/diagnostics
GUIDE_DIAGNOSTICS_SITE_METHOD = local
GUIDE_DIAGNOSTICS_LICENSE = AGPL-3.0-or-later
GUIDE_DIAGNOSTICS_DEPENDENCIES = python3

define GUIDE_DIAGNOSTICS_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/guide_diagnostics.py \
		$(TARGET_DIR)/usr/sbin/guide-diagnostics
endef

$(eval $(generic-package))

