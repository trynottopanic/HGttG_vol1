################################################################################
# guide-se-deck
################################################################################

GUIDE_SE_DECK_SITE = $(BR2_EXTERNAL_GUIDE_OS_PATH)/apps/semiotic_engine
GUIDE_SE_DECK_SITE_METHOD = local
GUIDE_SE_DECK_LICENSE = AGPL-3.0-or-later
GUIDE_SE_DECK_DEPENDENCIES = python3 guide-node-link-core

define GUIDE_SE_DECK_INSTALL_TARGET_CMDS
	$(INSTALL) -m 0755 $(@D)/guide_se_deck.py $(TARGET_DIR)/usr/bin/guide-se-deck
endef

$(eval $(generic-package))
