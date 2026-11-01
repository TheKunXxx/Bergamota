# 0155: firmware-only host services for equuleus

## What this test answers

0154 device run41284968037, commitc7e54f8, registered the WLAN PD listener
successfully. The response state was0x7fffffff, not UP0x1fffffff, and there
were no notifications. The next mode10 test keeps that listener and adds
PD mapper64/v1/instance1 and Qualcomm TFTP4096/v1/instance0. It will reveal
whether the modem queries the domain list or requests firmware files.
Neither receipt of a request nor successful file transfer proves Wi-Fi.
WLFW, ath10k and a network interface remain absent.

## Donor and licensing

Based on bsd/dev/mi8_hostsvc.c/h/k.c from youzjuzi/dipper-xnu at
4e82c709ea42ebb509fa101b52972fdc890b873e. Its license-inventory.json identifies
these original modules as MIT. Full yanei/contributors MIT notice is retained
in all three files and docs/licenses/DIPPER_HOSTSVC_MIT.txt. Original mi8 API
names are retained for comparison. The integration in equuleus_mss.c remains
an APSL-2.0 derivative, as in the previous patches.

This is an extraction, not a wholesale transplant: RMTFS handlers, partition
shadows, handles, replay cache, partition callbacks and shared-memory fields
are removed. Only endpoints1(TFTP) and2(PD mapper) are opened/published.
No QRTR service14 is advertised; no new SCM ownership transfer is added.

## Device and memory audit

Original equuleus-live.dtb reserves camera0x8bf00000/0x500000,
wlan_fw0x8e300000/0x100000, modem0x8e400000/0x7800000,
mba0x96900000/0x200000, and cont_splash0x9d400000/0x2400000.
The donor borrows the first2MiB of camera memory for RMTFS, sharing it with
MSS. Even though equuleus has the same camera reservation, that alone does
not establish that no firmware or device still uses it. Mode10 therefore
does not map, zero or share that region. Existing MPSS memory handling and
no-reclaim guard remain unchanged. RMTFS will need a separate memory and
backing-partition integration review; it may still be required for WLAN UP.

## Firmware adapter

Only reads from the already-mounted FAT16 `modem` partition are possible.
Normalized paths must be `image/` followed by one8.3-style basename of at
most12 characters, consisting only of ASCII letters, digits, dot, underscore
or hyphen; dot/dotdot, extra slashes, colon, backslash and control characters
are refused. Directories, empty files and files larger than8MiB are refused.
All offset/length checks use subtraction to avoid overflow. The module
normalizes Qualcomm's readonly/firmware/image prefix and logs missing files.
No firmware bytes are placed in the package. No Windows/Android host directory
is exposed, and no modemst/fsg/fsc/persist reads or writes are implemented.

TFTP supports RRQ, octet mode, option negotiation and ACKs. Block size is
capped at2048 bytes and window size at1. WRQ is explicitly rejected with an
access error, rather than acknowledged as a discarded successful write.
The donor's remaining dormant write-session code has no entry from WRQ and
there is no file-write callback in the API. Unknown service queries return
an empty domain list. The mapper advertises only modem root and WLAN PD,
instance180, using the donor's service associations. This table is a test
configuration, not proof of all firmware domain metadata on equuleus.

## Execution and bounds

Use sweetmss=10 with sweetwlan=4 and sweetwlandelay=120. Mode10 retains
servreg and uses a30-second/60000-poll budget, plus an already-running send's
existing timeout(up to5seconds). Before a second client send, the deadline
is checked again. Callbacks only queue work; the polling thread processes
one host request per iteration, preventing recursive/unbounded dispatch.
Only observed modem QRTR node0 is accepted. Queue8, maximum128 accepted
requests and128 response attempts per test; at most8 TFTP sessions. Limits
and peer/length violations are logged. No automatic timeout retransmission
is implemented; the remote may retry its request. All ports, queues and
sessions are destroyed before the GLINK transport. The existing modem
cooperative stop/AXI checks follow; lack of HALT ACK still prevents reclaim.

Mode8 remains GLINK-only; mode9 remains the servreg-only test. Other modes
and touch/display geometry are unchanged. Fully reboot into Android before
each test and use temporary fastboot boot, not flash.

## Host checks and device evidence

`python3 tools/tests/test-equuleus-hostsvc.py` replays0149..0155 using an
interior driver-list fixture, then compiles the actual module with ASan/UBSan.
It checks domain response encoding/offsets, malformed/unsupported QMI,
RRQ/OACK/block ACK transfers, WRQ/traversal/peer rejection, queue/send budgets,
reentrant enqueue, failed open/publish/allocation cleanup, truncated requests
and2000 mutations. It also tests the actual updated SMEM/FAT adapter and
22 board/mode/one-shot cases. Previous servreg and GLINK stages remain
independently testable. CI requires0155 to apply and checks the linked host
service entry points. Full XNU compilation and device behavior remain pending
when this package is prepared.

Look for `eqmss: port 0155`, `eqhs: mode10`, published64/4096, `mi8hs: pdm`,
`mi8hs: tftp rrq`, data/ACK/error lines, `mi8hs: summary`, `eqsr: summary`,
and the subsequent STOP/HALT output. No requests is also a useful result;
do not extend the time indefinitely or replace firmware/calibration files
by guessed names to hide errors.
