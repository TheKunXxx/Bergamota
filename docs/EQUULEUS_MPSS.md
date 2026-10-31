# Equuleus MPSS/SMP2P test (0150)

## Baseline and scope

Requires the corrected 0149 from user commit `9353292`, full-build run
`41194740293`. Device logs confirm mode 2 clocks/power and mode 5 MBA startup
(PBL=1, MBA=1), successful memory ownership transfer/reclaim and AXI idle.

0150 adds `sweetmss=6`: preflight the packed `modem.mdt` and all split-image
files, prepare APPS/modem SMEM and SMP2P buffers, copy/read back metadata at
MBA +1 MiB, authenticate metadata, load/zero MPSS segments into the verified
120 MiB carve-out, authenticate the complete image, and observe SMP2P.
The module remains off unless `sweetwlan=4` and an explicit MSS mode is set.
Modes 1, 2 and 5 remain available. No new persistent partition writes exist.

This is not ath10k or working Wi-Fi. GLINK buffers are allocated but there
is no GLINK transport, QRTR/RMTFS host service or WLFW client yet. Missing
services may prevent READY or cause a firmware failure; AUTH_COMPLETE and
READY are reported separately so the device test can identify that boundary.

## Source

SMEM/SMP2P and split-image loading are adapted from yanei's
`dipper-xnu` commit `4e82c709ea42ebb509fa101b52972fdc890b873e`,
`bsd/dev/mi8_rproc.c`, retaining the APSL-2.0 derivative classification of
0149. The existing license/provenance in `EQUULEUS_MSS.md` applies.

The port retains the verified UFS read adapter, SWEET persistent logging,
RPMh shared lock and poison handling. Metadata validation rejects truncated
or unsupported ELF32 headers, malformed program-header/hash layouts,
file/memory-size mismatches, overflowing 32-bit segment addresses and loads
outside the reserved MPSS memory. Segment file sizes are checked before any
processor startup. MPSS mappings are transient, Normal-NC, rounded to 16 KiB
pages and restricted to that carve-out.

## Bounded test and cleanup

After AUTH_COMPLETE, the test waits up to 15 seconds for SMP2P READY; when
READY appears it observes for 4 more seconds. It then requests cooperative
STOP, waiting up to 5 seconds for STOP_ACK. Reset/AXI halt and memory reclaim
follow the 0149 path. Failure to halt an AXI port prevents reclaim. A failed
TrustZone reclaim is logged and the region is not used again by this test.

The donor leaves CX/MX high votes in place rather than guessing the prior
state. Fully reboot between powered tests; do not re-enter this image from
a previous test without rebooting. Preserve the known-working boot image.

Next device arguments: `sweetwlan=4 sweetwlandelay=120 sweetmss=6`, keeping
the working native-display, 8-CPU, UFS root and touch arguments. Use temporary
`fastboot boot`. The root image does not need to be reflashed.

## Validation

- Patch replay against the exact source embedded in corrected 0149.
- AArch64 object compiled with Zig/Clang and mock XNU declarations, including
  real AArch64 assembly. This is not full XNU compilation/link verification.
- Real MDT parser: valid and relocated inputs; 212 truncations; 17 malformed
  header cases; 2000 deterministic mutation smoke cases under UBSan.
- Actual boot routine: 20 mock MBA/MPSS success/failure cases, including
  preflight, allocation, readback and ownership cleanup.
- Actual segment loader: 14 mock metadata/auth/ownership/read/map/READY
  failures, buffer cleanup and BSS zeroing.
- Actual SMEM/SMP2P helpers: allocation, malformed data, READY/fatal/timeout,
  STOP_ACK success/timeout and restart-feature negotiation.

Run `python3 tools/tests/test-equuleus-mpss.py`. Tests use the source from
0149 plus 0150, not a separate reimplementation. CI must apply 0150 and link
both `_equuleus_mss_probe` and `_equuleus_mpss_load`. The real kernel build
and hardware mode 6 have not yet been tested.
