################################################################################
#
# guide-wikipedia-core
#
################################################################################

GUIDE_WIKIPEDIA_CORE_SITE = $(BR2_EXTERNAL_GUIDE_OS_PATH)/apps/wikipedia
GUIDE_WIKIPEDIA_CORE_SITE_METHOD = local
GUIDE_WIKIPEDIA_CORE_LICENSE = AGPL-3.0-or-later
GUIDE_WIKIPEDIA_CORE_DEPENDENCIES = python3 ca-certificates

define GUIDE_WIKIPEDIA_CORE_INSTALL_TARGET_CMDS
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/usr/lib/guideos/wikipedia
	$(INSTALL) -m 0644 $(@D)/guide_wikipedia_app.py \
		$(TARGET_DIR)/usr/lib/guideos/wikipedia/
	$(INSTALL) -m 0644 $(@D)/guide_wikipedia_client.py \
		$(TARGET_DIR)/usr/lib/guideos/wikipedia/
	$(INSTALL) -m 0644 $(@D)/guide_wikipedia_model.py \
		$(TARGET_DIR)/usr/lib/guideos/wikipedia/
	$(INSTALL) -m 0644 $(@D)/guide_wikipedia_store.py \
		$(TARGET_DIR)/usr/lib/guideos/wikipedia/
	$(INSTALL) -m 0644 $(@D)/guide_wikipedia_bridge.py \
		$(TARGET_DIR)/usr/lib/guideos/wikipedia/
	$(INSTALL) -D -m 0755 $(@D)/guide_wikipedia_client.py \
		$(TARGET_DIR)/usr/bin/guide-wikipedia-data
endef

$(eval $(generic-package))
