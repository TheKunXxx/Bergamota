# Equuleus 0158: bounded TFTP RAM store

Builds on dipper-xnu 4e82c709ea42ebb509fa101b52972fdc890b873e's MIT host services (imported in 0155). Keep its source notices.

0157 device evidence: RMTFS service14 accepted three writes into RAM; QRTR grew to37 servers. TFTP rejected WRQ as read-only and exhausted the128-request shared host-service budget. WLFW45 was not observed. These are observed limitations, not proof that TFTP alone blocks WLAN.

0158 enables TFTP RAM writes only in existing sweetmss=12. Modes8/9/10/11 retain prior behavior. Use the0156 shim reservation and a full Android reboot before temporary boot. RMTFS sharing,60-second probe, fatal checks, STOP and no-reclaim guard are unchanged. Wi-Fi association and GPU are not implemented by this patch.

## Storage and protocol

Eight RAM files, each with a fixed2MiB capacity: maximum16MiB plus bounded protocol state. WRQ allocates before ACK. DATA is copied before ACK; duplicate matching blocks are acknowledged without appending, conflicting duplicates return an error, future blocks acknowledge the last accepted block.64-bit progress supports16-bit wire block wrap. Negotiated blocks are8..2048 bytes, window1. WRQ OACK is followed by DATA1; no-options WRQ starts with ACK0. Declared tsize must fit capacity and match the final byte count.

Completed files can be retrieved by RRQ and remain immutable until stop. Existing/incomplete filenames return error6 on another WRQ; eight occupied filenames return error3. Abandoned uploads consume a slot until stop, deliberately keeping storage bounded. No eviction or overwrite protocol is inferred from unobserved device traffic. Size/allocation failures return errors, never successful discarded writes. Firmware RRQ fallback remains read-only; no filesystem or partition write callback is added.

Names use the existing canonical image/ namespace, stripping leading slashes and known firmware prefixes. Empty/dot/traversal components, non-printable/non-ASCII characters, backslash and colon are rejected. RAM storage never resolves a host path. Logs show canonical filename, declared size and completion size, never content. All RAM file allocations are wiped before free after transport ports close.

TFTP has8192 received-request and reply attempts; PD mapper has independent512 limits. At most6 queued requests may be admitted by TFTP, leaving two of the8 slots for PD mapper. One request is dispatched per poll. Existing modes retain128 total attempts. There is no autonomous retransmit timer; peer retries drive retransmission, within the unchanged probe deadline.

## Validation

Run `python3 tools/tests/test-equuleus-tftp-ram.py` and `EQUULEUS_TEST_0158=1 python3 tools/tests/test-equuleus-glink.py`. The first replays0150..0158 on a fixture with interior driver-registration context, compiles the actual service with warnings-as-errors and ASan/UBSan, and tests upload/readback, OACK, duplicates/conflicts, out-of-order blocks, tsize, wire wrap, capacity, allocation failure, budget isolation, queue reservation, buffer wiping and2000 mutated requests. Prior0155 and0157 suites remain separate regression checks.

Host tests cannot establish modem compatibility or real Wi-Fi availability. Full XNU Actions build and a new device log are required. Expected new lines: `eqmss: port 0158`, `tftp wrq file=... RAM=...`, `RAM complete file=... bytes=...`. Capture the first rejected filename/options or size limit if WLAN remains down.
