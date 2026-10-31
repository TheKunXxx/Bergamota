# 0153 bounded GLINK/QRTR probe

## Donor and scope

Transport adapted from youzjuzi/dipper-xnu at
4e82c709ea42ebb509fa101b52972fdc890b873e, bsd/dev/mi8_glink.c and
mi8_glink.h. The donor marks these original modules MIT in its
license-inventory.json. Full yanei/contributors copyright and MIT text
are retained in both added source files and docs/licenses/DIPPER_GLINK_MIT.txt.
The original module/API names are preserved for easier upstream comparison.

Changes: local QRTR declarations replace the unavailable sys/redwood_qrtr.h;
the transport connects to equuleus's validated SMEM reader/writer and the
existing MSS test. No RMTFS/PD mapper/file service, WLFW, ath10k, SMMU or
network-interface implementation is included. No new partition access or
TrustZone memory ownership changes occur. This is not working Wi-Fi.

## Device-specific integration

Original equuleus-live.dtb: GLINK at SMEM0x86000000 size0x200000,
irq-reg-base0x1799000c, qcom,irq-mask0x1000. Use the existing IPC bit12.
The APPS/modem SMEM partition remains selected by the verified stride48
reader. Require descriptor478 exactly32B, TX479 and RX480 aligned8B,
64B..128KiB each, no overlap and fully contained in the2MiB SMEM window.
Only host TX FIFO and descriptor TX-head(+4)/RX-tail(+8) can be written.
All reads are restricted to these three validated items. Adapter violations
latch a fault, stop the polling loop and suppress subsequent notifications.

## Explicit mode8

Modes1/2/5/6/7 retain their previous behavior. Only sweetmss=8 enables this
probe, still requiring equuleus and sweetwlan=4. After MPSS AUTH_COMPLETE
and SMP2P READY, wait/poll for at most10seconds (also capped20000iterations),
perform VERSION/IPCRTR/intent/QRTR exchange and print discovered servers.
Check SMP2P liveness/fatal state every100ms, including before starting.
Close/destroy the host transport at the end, then use the existing
cooperativeSTOP and failed-halt memory guard. Mode8 uses mode6's halt
behavior; it does not force the unsuccessful mode7 isolation hypothesis.
The close sends a transport close request but is not a validated graceful
GLINK shutdown sequence; full reboot is mandatory between hardware tests.

Logs distinguish transport start from protocol evidence: start=1 only
means the local transport started. Look for VERSION exchange, 'IPCRTR open
both ways', 'qrtr hello' and service announcements before claiming a link.
Missing item480, no peer response or errors are useful results. No claim
that GLINK will resolve the modem AXI halt timeout is made.

## Validation and limitations

- Normal-context patch chain0149->0150->corrected0151->0152->0153, including
  new kernel source registration and headers.
- Actual imported transport under ASan/UBSan: VERSION/IPCRTR, zero-id peer
  intent, QRTR HELLO and server addition/removal, malformed FIFO marks,
  invalid OPEN/unknown commands, RX wrap. Allocation counter returns zero.
  LeakSanitizer disabled because the execution environment uses ptrace;
  ASan/UBSan remain enabled.
- Actual adapter: bounded polling; missing/overlapping/out-of-range items,
  fatal DSP, read failure, write allowlist and overflow rejection.
- Actual boot entry:18board/mode/one-shot cases, only mode8 enables GLINK.
- Previous0149/0150/0151/0152 suites pass unchanged. CI requires0153 source
  and linked equuleus_glink_probe/mi8_glink_start symbols.
- Full XNU compile and real device GLINK exchange are still pending.

Next device args: sweetwlan=4 sweetmss=8 sweetwlandelay=120, keeping the
working native-display/touch/UFS args. Full reboot into Android before
fastboot boot. No rootfs reflash. Capture SWEETLOG after returning to Android.
