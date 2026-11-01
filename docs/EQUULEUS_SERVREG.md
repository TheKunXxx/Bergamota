# 0154: bounded WLAN protection-domain service notifier

This is a diagnostic kernel test, not Wi-Fi support. The device's successful
0153 run41221650683 (commitb75a229) discovered service66/version1/instance180
at QRTR node0 port1. Mode9 now opens a QRTR client, registers a listener for
`msm/modem/wlan_pd`, observes its state, and acknowledges valid notifications.
No RMTFS, file server, PD mapper, WLFW, ath10k, SMMU or network interface is
added. No additional partition writes or SCM ownership operations are added.

## Source and wire format

Protocol adapted from `bsd/dev/mi8_rproc.c` in youzjuzi/dipper-xnu,
commit4e82c709ea42ebb509fa101b52972fdc890b873e, from the servreg section in
`patches/xnu-mi8.patch`. The donor's mi8_rproc derivative is APSL-2.0;
that identifier and provenance are retained in both new source files.
License text: `docs/licenses/APSL-2.0.txt`. The existing GLINK transport
retains its separate MIT notice.

QMI uses a seven-byte header: flags, little-endian transaction, message ID,
payload length. Register0x20 encodes TLV1 enable=1 and TLV2 the raw 17-byte
path, without NUL or nested length. Response TLV2 contains result/error;
optional TLV0x10 contains the current state. Indication0x22 requires TLV1
state32, TLV2 exact path, TLV3 notification transaction16. ACK0x23 sends
TLV1 path and TLV2 that notification transaction. State0x1fffffff is UP;
other values are logged and clear the local UP flag. Error9 is logged as
an error, not treated as success or hidden by trying unrelated paths.

## Integration and limits

`sweetmss=9` uses the existing authenticated MPSS/READY sequence, then the
same bounded SMEM GLINK adapter as mode8. The loop has a 20-second wall-clock
budget and 40000-iteration cap. A transport send already in progress may
extend this by its existing five-second timeout. The client makes at most
five registration attempts (two-second response/retry interval), and at most
32 total sends. Notification ACKs have an eight-entry queue; overflow and
response timeouts are logged. A lost ACK is not automatically retransmitted;
a repeated remote indication can queue a fresh ACK. This is a bounded probe,
not a permanent service daemon. No unregister handshake is claimed.

Mode8 remains the original ten-second GLINK-only test. Other existing modes
are unchanged. Mode9 retains the mode6 stop path and the no-reclaim guard:
if AXI is not quiescent, memory is not returned to HLOS. GLINK alone did not
resolve the modem HALT timeout on the device. Full reboot into Android is
required between hardware tests. Use temporary `fastboot boot`, not flash.

The parser requires an exact QMI frame length, complete TLVs, no duplicate
TLV types, exact mandatory field sizes and exact path. It checks the bound
node/port and correlates register/ACK responses with outstanding requests.
Node0 is valid. Endpoint removal clears pending work and state; transaction
serial and send budgets survive rebinds. Callbacks do not send recursively:
ACKs are queued for the polling thread. Requests establish their pending
transaction before calling send, which may synchronously deliver a response.
A later registration response cannot overwrite an already received state
notification. Unknown optional TLVs are skipped after structural validation.

## Validation and expected device evidence

`python3 tools/tests/test-equuleus-servreg.py` replays0149..0154, compiles the
actual client under ASan/UBSan, tests request bytes, peer/transaction rejection,
truncated/duplicate TLVs, UP/DOWN, queue limits, retries, synchronous callbacks,
service removal and 4000 mutated indications. It also runs the actual GLINK
transport, updated MMIO adapter, twenty-second bound, fatal/read failures,
write allowlist, board/mode gate and one-shot checks. Older tests can still
replay their original patch stages independently. Host mocks do not prove
real firmware compatibility. Full XNU compilation and mode9 device test are
pending when this package is prepared.

Look for `eqmss: port 0154`, `eqsr: service found`, `register sent`,
`register response`, optional `current state` / `notification state`,
`ack sent` / `ack response`, and the final `eqsr: summary`. A registration
success does not itself prove UP; an UP report does not prove usable Wi-Fi.
Missing service, error9, a DOWN state, or a timeout are useful diagnostic
results. Save the complete persistent boot log, including the following
STOP/HALT result; do not infer successful cleanup from the client summary.
