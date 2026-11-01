# Equuleus 0159: replaceable RAM files and TFTP diagnostics

## Why this follows0158

The0158 device log confirmed RAM writes of `readwrite/server_check.txt` (5bytes) and `readwrite/mcfg.tmp` (1byte), readback of the latter, and a WLAN PD UP notification with successful ACK. The host subsequently refused another WRQ for the existing `mcfg.tmp`. Several RRQs returned not-found without naming the requested file. QRTR listed39 servers but no WLFW service45. TFTP is an observed remaining limitation, not a proven complete explanation of missing Wi-Fi.

The pinned donor is `youzjuzi/dipper-xnu` commit `4e82c709ea42ebb509fa101b52972fdc890b873e`, MIT host services in `patches/xnu-mi8.patch`. Its WRQ path ACKs and counts discarded bytes; it does not implement durable or RAM-backed replacement.0159 preserves the imported protocol plumbing and notices, adding explicit RAM version handling rather than treating discarded bytes as saved data.

## Replacement semantics

A WRQ for a completed filename stages a separate RAM allocation. Only validated final DATA publishes the new version. Existing readers keep their immutable old version until completion or cancellation; later readers get the new current version. No disk writes are introduced. Failed allocation, rejected DATA, or cancelled upload leaves the completed current version intact. An active writer for the same name excludes a second writer; identical in-progress WRQ retries replay the appropriate ACK/OACK. After a completed write, another WRQ begins a new upload.

Garbage collection runs after dispatch, when reentrant transport callbacks can only have queued requests. It wipes and frees abandoned uploads and non-current versions without active readers. Completed sessions pointing to released storage are invalidated. Interrupted old readers can pin versions until their session is cancelled/reused or the bounded probe ends.

The existing ceiling remains eight simultaneous2MiB file buffers, including staging and pinned versions: maximum16MiB. Eight occupied buffers may cause a replacement to return a capacity error; old data remains available. No unbounded eviction or destructive in-place overwrite is used. The session limit8, TFTP/PD budgets8192/512, queue reservations, one-request-per-poll dispatch and60-second mode12 deadline remain unchanged. Modes10/11 retain their previous gates. RMTFS sharing, fatal checks, HALT and no-reclaim protection are untouched.

## Diagnostics

Validated missing RRQs now log canonical and requested filenames plus peer. Input filenames remain bounded and printable. Firmware read errors include canonical path, offset and size. Final RRQ ACK logs `RRQ complete file=... bytes=... RAM=...`, allowing full firmware delivery to be distinguished from partial progress. RAM completion includes `replaced=0/1`.

A dedicated completion log category avoids suppression by verbose ACK logs. Stop always emits host-service counters when a log callback exists: total requests/replies/rejections, TFTP/PD requests/replies, commits, replacements, completed RAM readbacks and missing files. It does not print file contents.

## Validation and device step

`python3 tools/tests/test-equuleus-tftp-replace.py` replays the real patch chain through0159, compiles the actual service with warnings-as-errors and ASan/UBSan, and exercises old/new simultaneous readers, duplicate WRQ/DATA, competing writer, allocation failure, cancellation,40 successive replacements, capacity refusal preserving old data, missing filename/summary logging, zeroed frees and2000 malformed requests.

`EQUULEUS_TEST_0159=1 python3 tools/tests/test-equuleus-glink.py` compiles/checks the modified adapter. Earlier0158 tests remain a regression suite for the earlier stage. These host tests do not prove firmware compatibility. Full XNU CI and a new temporary device boot/log are still required.

Use the0156 reserved shim and `sweetmss=12` after a full Android reboot. Expected marker: `eqmss: port 0159`. First inspect `tftp missing file=`, `RRQ complete`, `RAM complete ... replaced=`, the final counters, WLAN PD state and QRTR service list. Wi-Fi association and GPU acceleration remain subsequent work.
