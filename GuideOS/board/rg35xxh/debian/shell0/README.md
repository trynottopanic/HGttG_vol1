# Debian Guide Shell integration slice 0

This is the first production-shaped GuideOS component on the Debian foundation.
It proves one accountable owner for the built-in display and ordinary controls.
It is not the finished shell and contains no media player.

The image masks `getty@tty1.service`; serial console output remains available on
`ttyS0`. `guide-shell.service` owns `/dev/tty1`, `/dev/fb0`, the H700 gamepad and
volume keys. It never opens the dedicated power-key device. `systemd-logind`
retains that key as an independent orderly-poweroff path.

The restored seed's home screen exposes Media Foundation, System Status and Power Off. Media
Foundation honestly reports that the shared player is not installed. Power Off
requires a separate confirmation. Menu always returns home. No long press is
overloaded as navigation.

Current source additionally contains opt-in Wi-Fi Discovery and fault-tolerant
report destinations. `GUIDE_WIFI_DISCOVERY=1` enables the discovery choice;
the default is the baseline menu. The Shell 1 deployment profile keeps discovery
disabled and adds persistent boot evidence. See the current release record in
`GuideOS/DEBIAN_SHELL_1.md`; the earlier audit is a dated snapshot.

Each boot writes a bounded semantic record to the data and boot partitions.
Cleanup outcomes are saved after input and display release; cleanup failure does
not suppress an already confirmed power request. The direct framebuffer adapter
uses a whole-frame copy when the layout permits, but it is not a KMS page-flip
implementation and therefore does not claim tear-free video.

Physical acceptance requires repeated boot, navigation, service restart, hardware
Power response, confirmed menu shutdown, absence of getty/display interference,
and inspection of the final cleanup record.
