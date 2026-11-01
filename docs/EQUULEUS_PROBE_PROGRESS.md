# Equuleus 0162: bounded loading progress and stop reasons

The 0161 device test verified deep SDM845 hardware and software MCFG delivery. It finished with WLAN PD UP,39 QRTR servers and no WLFW45. The last recorded requests were still loading software configurations. Because completion messages are sampled, this does not establish whether all configuration transfers finished or whether the60-second outer deadline interrupted them.

## Behavior

Mode12 now has a180-second outer probe budget and360000 loop iterations, with the same500us delay. Other mode budgets remain10/20/30seconds. Both caps remain finite; an in-flight GLINK operation keeps its existing bounded transport wait and can extend wall time past the outer deadline until it returns. Fatal/SMEM fault checks and the stop/HALT/no-reclaim path are preserved. There is no automatic reboot or storage write.

The RAM-enabled TFTP request and reply-attempt caps rise from8192 to32768 to accommodate the longer probe. PD mapper retains its independent512 cap. Non-RAM host-service mode retains128 total requests/reply attempts. Queue capacity8, TFTP admission ceiling6, one request per poll and the16MiB RAM file ceiling are unchanged.

Mode12 sets the new GLINK quiet_data flag: successful data-send, intent advertisement, grant and completion chatter is suppressed. Errors, refused intents, server discovery and channel messages remain visible. Host-service routine ACK/data/option messages use the first4 then every1024 policy in RAM mode. Other log categories retain their existing sampling policy; filenames, errors and transfer completions remain available. Firmware behavior is not changed by this flag.

## New evidence in the log

`eqgl: exit reason=... elapsed_us=... polls=... budget_us=...` distinguishes deadline, poll-cap, DSP failure, allocation/start/publication failures and IO faults.

The host-service snapshot runs before queues/sessions/RAM are freed. It prints each live unfinished RRQ/WRQ (at most8): peer, filename, bytes submitted/stored, file size, ACK/sent blocks and pending OACK. For a WRQ without declared tsize, size is zero until completion; it is not a known total. RRQ bytes are bytes submitted through the last successfully sent block, not proof of final peer acknowledgement.

The progress summary includes completed RRQs, active readers/writers, queued requests, queue peak, successfully submitted DATA bytes (including retransmissions), transport send errors, dispatched requests with no response attempt, queue/request-budget/allocation drops and reply-cap refusals. A request without a response can be a normal duplicate, cancellation or stale ACK; the counter alone is not a protocol failure. Admission-drop counters may overlap. Existing per-endpoint request/reply and RAM counters remain in the stop summary.

`mi8_hostsvc_snapshot` performs no sends or state mutation. It is linked explicitly and included in the CI symbol check. It cannot claim all modem initialization is complete merely because active transfers reach zero.

## Validation

`python3 tools/tests/test-equuleus-probe-progress.py` replays through0162 and tests the actual service with ASan/UBSan and warnings-as-errors: snapshot stability/no sends, pending queues, active and completed transfers, exact DATA byte counts, send/no-response/allocation errors, request and reply cap reasons, independent PD budget and old-mode preservation.

`EQUULEUS_TEST_0162=1 python3 tools/tests/test-equuleus-glink.py` runs actual transport protocol checks with quiet mode both off/on and confirms errors remain logged. Adapter tests exercise deadline, frozen-clock poll-cap and DSP-fault exit records plus bounded unprepared-RMTFS refusal. Full XNU CI and phone validation remain necessary.

Use sweetmss=12 and the reserved shim after a full Android reboot. Wait at least6minutes after temporary boot before returning to Android for the persistent log. Inspect exit reason, active filenames, completed counts and budget drops, then the final QRTR/WLFW list. SpringBoard Motion/HomeKit privacy-description crashes remain a separate issue; this patch does not alter app metadata.
