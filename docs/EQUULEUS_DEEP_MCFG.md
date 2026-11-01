# Equuleus 0161: deep MCFG paths and plus-name aliases

The 0160 phone log confirmed that both MCFG digest files exist and are readable, and that WLAN firmware, mbn_hw.txt and oem_sw.txt were fully delivered. Further requests exceeded the adapter's eight-component limit; several names contain 7+7_mode. Prior not-found responses therefore did not establish that those files were absent.

0161 raises the firmware path and FAT lookup limits to 24 components and 255 bytes. It accepts '+' within the same bounded component shape (base up to eight characters, extension up to three). The image/modem_pr/ namespace restriction, direct image/ firmware files, character allowlist, rejection of dot/traversal/empty components, directory cluster checks, and subtraction-based file-read bounds remain in place.

A plus-containing name can use a VFAT name record associated with a short alias. The reader now matches a single VFAT slot containing up to 12 ASCII characters. It requires ordinal 0x41, type zero, cluster zero, correct UTF-16 positions and terminator/padding, and the checksum of the immediately following short entry. ASCII comparison ignores case. State survives a directory-cluster boundary and is reset by deleted or intervening entries. Multi-slot, Unicode, or arbitrary longer names are not enabled. Ordinary short-name lookup still works. Format reference: Microsoft's FAT specification, sections on long-name entries/checksum: https://www.cs.fsu.edu/~cop4610t/assignments/project3/spec/fatspec.pdf . The implementation is local code, not copied from a filesystem driver.

No firmware is fabricated or written to storage. MCFG values are not changed. RMTFS, RAM TFTP replacement, SCM ownership, mode gates, stop/HALT/no-reclaim handling and the 60-second GLINK deadline are unchanged. The port marker is 0161.

## Validation

`python3 tools/tests/test-equuleus-deep-mcfg.py` replays the patch chain through 0161 and compiles actual FAT lookup/read, firmware callbacks and TFTP path parsing with warnings-as-errors, ASan and UBSan. Every unique nested missing MCFG path from the 0160 log is checked against a synthetic FAT fixture and read back with exact bytes. Additional tests cover 24 versus 25 components, paths over 255 bytes, plus names, ordinary firmware, aliases, invalid names, corrupt directory clusters, read/mount failure and zero outstanding allocations.

A real VFAT record/short-alias fixture tests plus-name lookup, checksum/type/cluster/Unicode rejection and a name record at the end of one cluster followed by its alias in the next. This fixture does not prove the phone uses the same directory representation. The next phone boot must establish actual availability.

`EQUULEUS_TEST_0161=1 python3 tools/tests/test-equuleus-glink.py` compiles and checks the updated adapter's bounds, deadline and unprepared-RMTFS refusal. Full XNU CI and real device testing are still required.

Use the existing reserved shim, sweetmss=12 and a full Android reboot before temporary boot. Allow five minutes before returning to Android to capture a more complete log; the previous log lacked the final summary. Inspect full MCFG .mbn RRQ completion, remaining missing paths, WLAN PD state and the final QRTR/WLFW list. Missing readwrite/ota_firewall/ruleset remains unexplained and is not fabricated. SpringBoard privacy-description crashes are a separate issue and are not changed here.
