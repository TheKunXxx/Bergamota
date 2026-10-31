# Equuleus MSS/MBA bring-up (0149)

This is an experimental prerequisite for WCN3990 Wi-Fi, not a Wi-Fi driver.
The module is off by default. Existing `sweetwlan=0` boots do not enter it.

## Source and adaptation

The FAT16 reader, QMP, ARC-level RPMh, SCM ownership, GCC/reset and MBA
sequence are adapted from `bsd/dev/mi8_rproc.c` in
[dipper-xnu](https://github.com/youzjuzi/dipper-xnu), commit
`4e82c709ea42ebb509fa101b52972fdc890b873e` (yanei, 2026).
The donor classifies this XNU/HackiOS derivative as APSL-2.0 in its
`license-inventory.json`; the license is included in
`docs/licenses/APSL-2.0.txt`. This port does not include the donor GPU tables.

Hardware addresses were compared against the supplied live equuleus DTB:

| Resource | Address/range |
| --- | --- |
| MBA reserved memory | `0x96900000`, 2 MiB |
| MPSS reserved memory | `0x8e400000`, 120 MiB |
| QDSP6SS / RMB | `0x04080000` / `0x04180000` |
| APPS RSC | `0x179e0000`, TCS offset `0xd00` |
| SMEM | `0x86000000`, 2 MiB |

The existing 0148 device test confirms the APPS/modem partition at SMEM
offset `0xb9000`, size `0x7c000`, and readable MBA/MPSS/WLAN firmware.
It does not prove that any remote processor has started.

Changes from the donor:

- UFS access uses `sweet_ufs_read_part`; it only reads the `modem` partition.
- Diagnostics use `printf`, captured by the existing SWEET persistent log.
- The temporary MBA mapping uses stock XNU `io_map` with Normal-NC memory
  and is unmapped before ownership changes. No HackiOS loader ABI is used.
- Direct ARC requests share `sweet_rpmh.c`'s transaction lock with the
  existing regulator driver. Unknown completion poisons the shared bus;
  further requests are refused until a reboot.
- There is no ADSP startup, full MPSS image load, GLINK, host-service,
  WLAN-SMMU or ath10k path in this module.
- Donor cleanup-skip boot arguments are removed. Modes are allow-listed.

## Modes and next device test

The module is called on the existing delayed WLAN thread only when
`sweetwlan=4`. It additionally checks `xiaomi,equuleus` compatibility and
requires one of these explicit `sweetmss` modes:

| Argument | Operation |
| --- | --- |
| absent / `sweetmss=0` | No MSS operation |
| `sweetmss=1` | Read GCC, ARC level metadata and TCSR halt ports |
| `sweetmss=2` | QMP modem vote, ARC power votes, enable/test/disable clocks; no Q6 startup |
| `sweetmss=5` | Read/copy MBA, transfer reserved-memory ownership, start MBA on Q6, inspect status, attempt shutdown/reclaim |

The first powered device test should use `sweetwlan=4 sweetmss=2
sweetwlandelay=120`, retaining the working native-display/touch arguments.
Use a temporary `fastboot boot` image; the root image need not be reflashed.
Do not use mode 5 until the mode-2 log has been reviewed.

The donor leaves high CX/MX votes in place because the original votes are
unknown. A full device reboot is required between powered tests. Mode 5
can leave memory assigned to MSS if shutdown or TrustZone reclaim fails;
the diagnostic log reports this condition. Its cleanup is not yet tested
on equuleus. No modem calibration/NV or other persistent partition writes
are implemented.

## Validation and CI

- Patch replay checked against reconstructed WLAN/RPMh sources through
  0148; the `bsd/conf/files` hunk checked against its known surrounding
  lines (not a full local XNU tree).
- The full new module compiled to AArch64 with Zig/Clang using mock XNU
  declarations. This checks C/assembly, not real XNU header compatibility
  or kernel linking.
- `python3 tools/tests/test-equuleus-mss.py`: 13 mock MBA success/failure
  cases check buffer release, unmapping before ownership changes, cleanup
  and refusal to reclaim if an AXI port does not halt.
- Shared-lock busy/release/poison behavior checked in a host C harness.
- Workflow YAML parsed; mandatory-patch rejection and guard idempotency
  checked on the pinned build script.

Full XNU compilation/linking and all new hardware modes remain pending.
CI now runs `tools/equuleus-ci-verify.py`: failed application of 0148/0149
is fatal, and successful builds must contain the changed sources and the
linked `_equuleus_mss_probe` symbol before being reported as successful.
