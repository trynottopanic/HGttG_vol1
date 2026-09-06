################################################################################
#
# guide-node-link-core
#
################################################################################

GUIDE_NODE_LINK_CORE_SITE = $(BR2_EXTERNAL_GUIDE_OS_PATH)/apps/node_link
GUIDE_NODE_LINK_CORE_SITE_METHOD = local
GUIDE_NODE_LINK_CORE_LICENSE = AGPL-3.0-or-later
GUIDE_NODE_LINK_CORE_DEPENDENCIES = python3 alsa-lib

define GUIDE_NODE_LINK_CORE_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_LDFLAGS) \
		-o $(@D)/guide-audio-control $(@D)/guide_audio_control.c -lasound
endef

define GUIDE_NODE_LINK_CORE_INSTALL_TARGET_CMDS
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/usr/lib/guideos/node-link
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/usr/lib/guideos/media/bin
	$(INSTALL) -m 0644 $(@D)/guide_node_client.py \
		$(TARGET_DIR)/usr/lib/guideos/node-link/
	$(INSTALL) -m 0755 $(@D)/guide_node_bridge.py \
		$(TARGET_DIR)/usr/lib/guideos/node-link/
	$(INSTALL) -m 0755 $(@D)/guide-audio-control \
		$(TARGET_DIR)/usr/lib/guideos/media/bin/
endef

$(eval $(generic-package))
