# Equuleus0160: nested firmware paths

The0159 device log confirmed full delivery of wlanmdsp.mbn (3645892bytes), WLAN PD UP and39 QRTR servers. WLFW45 remained absent. It also exposed missing nested MCFG requests and vendor firmware aliases. The initial missing RAM mcfg.tmp is expected before its first upload. The second WRQ was accepted but no completed replacement or RAM readback was recorded; these are not claimed as device successes.

## Change

The existing FAT16 reader already traverses directories; the firmware adapter restricted requests to a single basename.0160 permits bounded, exact8.3 components under image/modem_pr/, retaining direct image/ files. Maximum path length127bytes and total lookup depth8. Arbitrary image/a/b trees and image/readwrite remain outside the firmware adapter. RAM file handling is unchanged.

FAT lookup now validates components before converting to8.3, preventing silent truncation such as abcdefghi into abcdefgh. Empty/dot/traversal components, excess dots, overlong base/extension and unsupported characters are rejected. Directory clusters must be inside the data-cluster range; zero cannot redirect nested traversal into the root. Long filename entries remain unsupported. The requested modem_pr/mcfg/configs/mcfg_hw/mbn_hw.dig and mcfg_sw/mbn_sw.dig fit strict8.3.

TFTP normalizes the observed /readonly/vendor/firmware_mnt/image/ and /readonly/vendor/firmware/ aliases to image/, alongside the existing /readonly/firmware/image/ prefix. No files are fabricated and no filesystem writes are introduced.

In mode12, a read-only MCFG audit prints size, lookup status and a small-read status for both requested paths. It prints no contents. This establishes on-device presence/readability only after the next test; current host tests cannot establish that the files exist on this phone's partition. Missing OTA firewall rules are not invented or treated as a proven WLAN blocker.

No changes to RMTFS, SCM ownership, HALT/no-reclaim handling, RAM replacement, mode gates or the60-second transport deadline. The separate SpringBoard NSMotionUsageDescription crash is outside this firmware-path change.

## Checks

`python3 tools/tests/test-equuleus-firmware-paths.py` replays0150..0160 and compiles actual FAT lookup/read, firmware callbacks and TFTP parser with ASan/UBSan and warnings-as-errors. An in-memory FAT16 fixture contains nested HW/SW files and direct WLAN firmware; tests verify exact content, aliases, invalid names, bounds, corrupt directory clusters, mount/read failures and cleanup. This is a synthetic fixture, not a captured phone filesystem.

`EQUULEUS_TEST_0160=1 python3 tools/tests/test-equuleus-glink.py` checks the actual updated adapter, including its bounds/deadline and refusal to use unprepared RMTFS. Full XNU build and temporary phone boot remain required.

Use existing reserved shim and sweetmss=12, after a full Android reboot. Expected marker: eqmss: port 0160. Inspect eqfw: MCFG lines, missing filenames, full RRQ completion, WLAN PD state and WLFW service45. ENOENT means the requested short-name path still cannot be resolved; inspect the actual partition layout before assuming another file or inventing substitute data.
