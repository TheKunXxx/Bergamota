# 0157: bounded RMTFS using RAM snapshots

0156 actual device run41293181051 passed the CPU preflight: data PA0xa8008000,
2MiB, canaries/readback OK, named UFS reads successful. Confirmed LUNs are5
for modemst1/modemst2/fsc and4 for fsg. That test did not prove SCM sharing.

## Scope and provenance

New sweetmss=12 prepares complete RAM copies before starting the modem, then
adds RMTFS14/v1/instance1 to the existing GLINK, servreg, PD mapper and TFTP
test. It attempts SCM sharing of the verified buffer only after authenticated
MPSS reports SMP2P READY. No WLAN interface, WLFW or ath10k is added. Missing
RMTFS remains a hypothesis for WLAN not starting, not a guarantee of UP.

Wire semantics are adapted from mi8_hostsvc.c in youzjuzi/dipper-xnu,
commit4e82c709ea42ebb509fa101b52972fdc890b873e. Its MIT copyright/permission
notice is retained in the new portable equuleus_rmtfs.c; the existing full
license is docs/licenses/DIPPER_HOSTSVC_MIT.txt. The separate implementation
adds eager snapshots, node checks, atomic batch validation, bounded polling,
replay handling and cleanup. Integration in equuleus_mss.c remains APSL-2.0.

## Storage isolation

The only storage callbacks are named part_size and part_read. There is no
part_write, file_write, erase or flush-to-disk API. Exact required sizes:
modemst1/modemst2/fsg each8MiB and fsc256KiB. All24.25MiB are read into RAM
in64KiB chunks, before any new modem power/SCM operation. A missing partition,
size mismatch, failed chunk or allocation failure aborts preparation and
wipes/frees all partial snapshots. No contents, hashes, serials or credentials
are logged or exported. Snapshots are wiped before their heap is freed.

The donor's two /boot/modem_fsg_oem_1 and _2 paths are explicit1MiB blank
RAM areas. They do not read or stand in for any guessed physical partition.
A READ copies RAM snapshot -> shared buffer. A WRITE copies shared buffer ->
RAM snapshot. SYNC acknowledges RAM state only; it is not persistence. All
such changes are discarded after the bounded test or reboot. The service is
therefore a diagnostic volatile backing, not a production persistent NV store.

## Ownership and lifecycle

Uses the same header/guard/data layout and shim reservation stamp156 as0156;
no low-memory range or geometry changes. Kernel preparation checks the stamp,
header, guards and a completely zero buffer. With missing reservation, dirty
buffer or failed full snapshot, the test returns before MSS survey/power.
The full buffer remains2MiB; the metadata/canary pages are never shared.

After MPSS AUTH/READY and GLINK start, assign_mem requests HLOS+MSS ownership
of PA0xa8008000/0x200000 (source HLOS mask8, destination0x8008). RMTFS is
published only after SCM reports success. A failed SCM call is treated as
uncertain: no retry, no service publication and no reuse in this boot.
Publication failure also retains the pool. Even if later AXI halt succeeds,
this diagnostic does not reclaim, zero, unmap or free the shared pool. It is
reserved outside the XNU allocator until full reboot. This avoids the known
HALT failure/unsafe-reclaim path. It is intentionally not a general allocator.

At the end, RMTFS port/queued requests close before GLINK destruction and
cooperative modem stop. Only CPU-owned snapshot/cache memory is freed; the
modem never receives physical addresses for those heap objects. The existing
MPSS/MBA HALT/no-reclaim guard remains unchanged. Full reboot into Android
is required between hardware tests; use temporary fastboot boot, not flash.

## Wire behavior and limits

QMI messages1OPEN,2CLOSE,3RW_IOVEC,4ALLOC_BUFF,5DEV_ERROR,6SYNC; exact frame
length and complete, nonduplicate TLVs are required. OPEN accepts the six
exact donor paths. Handles bind to modem QRTR node0, allowing its observed
cross-port requests. ALLOC uses DT client-id1 rather than an OPEN handle and
returns the shared physical address in TLV0x10 as64-bit. Unknown client IDs,
paths, handles, directions and commands fail explicitly.

Every vector is checked with64-bit arithmetic against both snapshot and
shared-buffer bounds before any vector is applied. Sector units are512B.
Empty vectors are refused; aggregate bytes per batch cannot exceed2MiB.
Only node0 and valid remote ports are accepted. Queue8, handles32, exact
request/peer replay cache16, request maximum8192B, accepted request and reply
budgets4096 each. Replayed OPEN/RW/CLOSE requests resend the cached response
without reapplying mutations. Temporary allocation errors are not cached.
Callbacks only enqueue; one request is processed per poll, including when a
send pumps a new callback. Polling is single-threaded, not a general concurrent
server API.

Mode12 has a60-second/120000-poll loop after READY. Deadlines are checked
between RMTFS, firmware-service and servreg work. One in-flight transport send
can extend the deadline by its existing timeout(up to5seconds). Snapshot
preparation and existing MPSS boot/stop have their own preceding/following
work. Counters and at most the first20 read/write batches are logged; no NV
bytes are included. Other modes, including mode11 preflight, remain available.

## Tests and build

Host tests replay0149..0157 with interior driver-list context. Actual module
ASan/UBSan checks cover full388-chunk snapshots, read/write-to-RAM, ALLOC and
client-id, cross-port handles, exact replay, invalid-last-vector atomicity,
bounds/overflow/aggregate limits, OEM RAM, CLOSE/SYNC/DEVERR, queue/handle/
request caps, malformed TLVs, allocation/read/open/publication cleanup and
2000 mutated requests. Twelve actual kernel-integration cases check contract,
SCM-before-publish, failed/uncertain share, no retry, preparation-before-power,
mode11 preservation, board gate and one-shot behavior. The actual modified
GLINK adapter is also compiled/tested. Earlier0150..0156 tests remain separate
regressions. None of these host mocks proves real firmware compatibility.

The build helper preserves/applies the verified volatile-field loader fix
that avoided compiler-generated memcpy. It performs a complete local shim
compile/link using the previous0156 payload before committing/pushing and
submitting a new XNU build. This local image is only a build check; do not boot
it as the new mode12 image. After successful CI, create a fresh0157 payload
using sweetmss=12 and build shim with EQUULEUS_RMTFS_RESERVE=1.

Required0157 patch application and linked RMTFS entry points are checked by CI.
Full XNU compilation and the on-device SCM/RMTFS test are pending when this
package is prepared. Look for snapshot-ready, SCM result, published14,
OPEN/ALLOC/RW counters, QRTR servers, servreg state and the final STOP/HALT log.
Keep the complete log even on failure; do not force ownership changes or
substitute firmware/calibration files to hide a rejected request.
