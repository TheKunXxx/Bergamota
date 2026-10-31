# 0152: explicit HALT request on all three MSS AXI ports

## Device evidence

User7e59cef/run41217836846 completed0151 without a recorded panic.
All28segments loaded549ms, MBA4, READY2 after36.372ms, STOP_ACK0xa
21.732ms. All7checked GCC clocks stayed on. The modem HALTREQ reads1,
but ACK/IDLE stay0 after1s and IDLE stays0 after reset. No reclaim occurred.

The original equuleus-live.dtb (495740B) has /soc/qcom,mss@4080000:

| reg-name | physical address |
|---|---|
| halt_q6 | 0x01f63000 |
| halt_modem | 0x01f65000 |
| halt_nc | 0x01f64000 |
| restart_reg | 0x0c2b0000 |
| pdc_sync | 0x0b2e0100 |
| alt_reset | 0x04180044 |

These match the current driver. Its reg resources advertise8B for halt
windows, but downstream code also accesses IDLE at+8; the short resource
length alone does not establish a wrong register offset.

## One isolated hypothesis

MiCode/Xiaomi_Kernel_OpenSource, dipper-o-oss,
drivers/soc/qcom/pil-msa.c pil_mss_shutdown calls halt on Q6, modem, NC.
pil-q6v5.c pil_q6v5_halt_axi_port unconditionally asserts HALTREQ, waits
for HALTACK, inspects IDLE and clears HALTREQ. Our imported newer-style
helper skips a port that is idle already. Q6/NC were both skipped in0151.

0152 independently changes only this choice in explicit sweetmss=7:
request HALT on every port in the same existing order, even if IDLE1.
Success requires request readback1, ACK nonzero and IDLE nonzero while
request is held. Mode6 retains its previous early-idle behavior. Timeouts,
reset/clock ordering and failed-halt no-reclaim guard are unchanged.
This is a hypothesis test, not a proven fix. No GPL source body was copied.

## Validation

- Normal-context git apply replay0149->0150->corrected0151->0152.
- Actual HALT implementation:14mode/scenario cases compiled with Werror
  and UBSan, covering initially idle ports, no ACK, ACK without IDLE,
  unlatched request and IDLE transitions on release.
- 0149/0150/0151 regression suites pass. CI requires0152 source marker,
  explicit mode7 gate and linked _equuleus_mss_halt_all symbol.
- Full XNU compile and device result pending.

Use sweetwlan=4 sweetmss=7 sweetwlandelay=120 and established native
screen/touch/UFS args. Full reboot first, temporary fastboot boot only.
No rootfs update. Capture SWEETLOG after test. If any port fails, do not
force memory reclaim. GLINK transport/QRTR/WLFW/Wi-Fi remain absent.

Source references:
https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/dipper-o-oss/drivers/soc/qcom
https://android.googlesource.com/kernel/common/+/4b95dc87362aa57bdd0dcbad109ca5e5ef3cbb6c/arch/arm64/boot/dts/qcom/sdm845.dtsi
