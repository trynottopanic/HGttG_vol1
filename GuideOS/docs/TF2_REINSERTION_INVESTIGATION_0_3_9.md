# TF2 reinsertion clock-timeout investigation, 0.3.9

27 September 2026. Historical investigation below; a driver/initial-clock
correction candidate is now built and tested in software. See
[TF2_DRIVER_CANDIDATE_0_3_9.md](TF2_DRIVER_CANDIDATE_0_3_9.md) for current build,
installation and physical acceptance evidence. No permanent hold-awake policy
is part of the candidate.

## Evidence and ownership

The returned physical kernel log in `build/card-install-followup-0/kernel-previous.log`
shows enumeration at 53.532 s, removal at 76.924 s, and seven clock-update failures
at 139.156--143.720 s. No second enumeration follows. The storage service remains
the sole mount owner; changing its polling or retrying mounts cannot create the
missing kernel block device.

The local source inspected was
`/home/hacker/guideos-work/debian-h700-kernel/linux-7.2.7/drivers/mmc/host/sunxi-mmc.c`,
SHA256 `e549934a4e1e2c7fe97d7206ad7ef04af5e7abe0a300ef2dc9db9586d4c0488e`.
This identifies the inspected source, not proof of a new kernel built or installed.

- `sunxi_mmc_oclk_onoff`, lines 662--705, waits 750 ms for SDXC_START to clear
  after a clock-only command. The roughly 756--768 ms physical error spacing is
  consistent with this bounded wait being exhausted repeatedly.
- `sunxi_mmc_clk_set_rate` first disables the card clock before setting its new
  rate. The existing log does not distinguish clock disable from clock enable,
  or show the command/status registers and clock parent at failure.
- The H616-compatible configuration already sets `mask_data0=true` and uses new
  timings. Adding that flag again is not a supported repair.
- Runtime autosuspend is 50 ms. Suspend disables interrupts, resets the host and
  disables clocks; resume enables clocks, initializes registers and restores
  width/clock. Resume currently returns success even if `sunxi_mmc_set_clk`
  records `host->ferror`. That is an error-reporting concern, but does not prove
  the reason the physical controller stopped completing clock updates.
- MMC core claims runtime power before host work. Therefore the absence of a
  direct runtime-resume call inside `set_ios` alone does not prove a missing
  power reference.
- Device-tree aliases map external Linux `mmc1` to controller `4022000.mmc`.
  Seed is `4020000.mmc`; Wi-Fi is `4021000.mmc`. Never target controllers by
  a guessed numeric Linux host name or reset all hosts.

The inspected mechanism agrees with the [upstream sunxi driver](https://github.com/torvalds/linux/blob/master/drivers/mmc/host/sunxi-mmc.c).
Neither this comparison nor the old timeout message establishes an H700 fix.

## Next physical discrimination

`build/release-0.3.9-startup/tf2-power-observe.py` is a bounded diagnostic helper.
It is not enabled at boot or copied into the candidate. Its default is read-only
power/card-presence sampling for 120 seconds. Run on the Deck, alongside the
kernel journal, through absent -> insertion -> removal -> reinsertion cycles.

A separate `--hold-awake` run temporarily sets **only**
`/sys/bus/platform/devices/4022000.mmc/power/control` to `on`, starting before the
first insertion, and restores the exact previous policy in `finally` on normal
completion, interruption or a handled error. The option is an experiment, not a
permanent workaround. It does not reset, unbind, mount, write card data, or alter
Seed/Wi-Fi power policy. A forced kill/power loss bypasses userspace cleanup;
the policy is runtime-only and resets on reboot. If TF2 is already wedged, start
the comparison on a fresh boot rather than trying resets during the test.

Compare at least three cycles per condition. If only the hold-awake condition
works, that strengthens the runtime power/clock restoration hypothesis; it does
not distinguish the exact register/clock sequencing defect. If both fail, inspect
clock parent/rate, regulator state, CD input and timeout registers next. A useful
instrumented kernel would record clock enable/disable direction, ios power/clock,
CMDR/CLKCR/STATUS and resume result only on TF2 failures. Avoid continuous tracing.

Physical repeated-cycle acceptance remains required. Do not promote this
investigation into a corrected-driver claim or alter the mount-owner contract.

## Physical cold-boot failure after storage startup repair

27 September, Wi-Fi report `inspect-20260927-073316.json` in the private
live-link evidence directory: storage and native player are active with zero
restarts. The kernel reports `sunxi-mmc 4022000.mmc: fatal err update clk timeout`
at 5.527 s, before storage starts at 11.011 s. This establishes that the timeout
also occurs on boot; it is not limited to repeated insertion. Both card-detect
GPIOs read low (active), while the external-card regulator GPIO reads low.
Those GPIO observations do not establish whether power loss is the cause or a
consequence of failed initialization. A single live reinsertion was requested
to test recovery, without changing controller or power policy.

The owner then confirmed: "Card now recognized, and media is playing correctly
from it." Follow-up Wi-Fi report `inspect-20260927-073438.json` shows external
SDXC enumeration at 128.788 s and its partition at 128.905 s, without a storage
service restart. Thus a single reinsertion recovered this boot's failure. It
does not establish reliable cold-boot detection or repeated insertion recovery.
