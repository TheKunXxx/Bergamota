# 0151 MPSS stop diagnostics

## Observed boundary

User kernel b5f64cd, run41207358147: packed MDT authenticated, all 28
segments loaded, MBA AUTH_COMPLETE=4, SMP2P READY=0x2 and STOP_ACK=0xa.
Q6 and NC ports were idle. Modem AXI at TCSR+0x5000 returned ACK=0,
IDLE=0 after 1000 ms. The existing guard correctly refused SCM memory
reclaim. This is not working Wi-Fi or a clean modem teardown.

0151 does NOT claim to fix the missing modem AXI acknowledgment. It captures
clock status and REQ/ACK/IDLE before STOP, after STOP, before HALT, after HALT
and after reset, plus RMB/PDC/AOSS state while the modem is not reset.
RMB is not read after reset; no extra MMIO reads occur after clocks go off.
Each diagnostic mapping is released. The existing boot/reset/clock ordering,
HALT timeout and failed-halt memory ownership guard are retained.

## Corrected observation race

The previous helper read IDLE for its return value *after* clearing HALTREQ.
Like Linux q6v5proc_halt_axi_port, 0151 samples IDLE while HALTREQ is held,
then clears it. It also verifies the asserted request reads back as 1.
A post-clear IDLE transition cannot turn a failed halt into success.
ACK alone does not prove IDLE; failure still prevents all memory reclaim.
This race is not proven to explain the device's ACK=0/IDLE=0 failure.

Source comparison: Linux drivers/remoteproc/qcom_q6v5_mss.c,
q6v5proc_halt_axi_port and q6v5_mba_reclaim; SDM845 has no qaccept register
sequence. The established 0149 APSL-2.0 provenance remains unchanged.

## Validation and next device test

- Replay 0149 -> 0150 -> 0151 checked with git apply, normal context.
- Actual HALT function compiled with warnings as errors and UBSan; seven
  MMIO scenarios, including timeout, unlatched request and IDLE changes on
  request release. Actual snapshot function: 25 phase/map-failure cases.
- Existing 0149/0150 suites pass. Full XNU build and real hardware remain
  unverified until the next GitHub run/device test.
- CI requires 0151 to apply, the new source marker, and linked symbol
  _equuleus_mss_stop_snapshot. An old cached kernel cannot pass this check.

Keep sweetwlan=4 sweetmss=6 sweetwlandelay=120 with the established native
screen/touch/UFS arguments. Full device reboot before this test, temporary
fastboot boot only. No rootfs or partition flash needed. Save SWEETLOG after
returning to Android. Do not force SCM reclaim if a port does not halt.

Interpretation: compare whether modem IDLE is already zero before STOP,
whether clock status changes across STOP_ACK, whether HALTREQ reads back,
and whether TCSR state changes after reset. These observations guide the
next targeted change; GLINK/QRTR host services are still absent.
