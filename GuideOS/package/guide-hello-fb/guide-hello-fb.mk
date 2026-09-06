################################################################################
#
# guide-hello-fb
#
################################################################################

GUIDE_HELLO_FB_SITE = $(BR2_EXTERNAL_GUIDE_OS_PATH)/package/guide-hello-fb/src
GUIDE_HELLO_FB_SITE_METHOD = local
GUIDE_HELLO_FB_LICENSE = AGPL-3.0-or-later, Bitstream-Vera
GUIDE_HELLO_FB_LICENSE_FILES = assets/DejaVu-Fonts-LICENSE.txt

define GUIDE_HELLO_FB_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) -static -Wall -Wextra -Werror \
		-o $(@D)/guide-hello-fb $(@D)/guide-hello-fb.c \
		$(@D)/cartridge.c $(@D)/installer.c $(@D)/wifi.c
endef

define GUIDE_HELLO_FB_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/guide-hello-fb \
		$(TARGET_DIR)/usr/sbin/guide-hello-fb
	$(INSTALL) -D -m 0644 $(@D)/assets/guide-globe-emblem-256.rgba \
		$(TARGET_DIR)/usr/share/guideos/guide-globe-emblem-256.rgba
	$(INSTALL) -D -m 0644 $(@D)/assets/guide-rose-seal-250.rgba \
		$(TARGET_DIR)/usr/share/guideos/guide-rose-seal-250.rgba
	$(INSTALL) -D -m 0644 $(@D)/assets/DejaVuSans.ttf \
		$(TARGET_DIR)/usr/share/guideos/fonts/DejaVuSans.ttf
	$(INSTALL) -D -m 0644 $(@D)/assets/DejaVu-Fonts-LICENSE.txt \
		$(TARGET_DIR)/usr/share/licenses/guideos/DejaVu-Fonts-LICENSE.txt
endef

$(eval $(generic-package))
