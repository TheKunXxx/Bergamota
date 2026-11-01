# 0156: owned low-memory pool and RMTFS backing preflight

0155 actual device result: PD mapper request/reply works, no TFTP requests,
WLAN listener registered but state0x7fffffff, no UP notification. RMTFS is
still the next hypothesis, not a proven missing dependency.

## Why a separate preflight

Android's UIO reports rmtfs0xf7301000/2MiB. That is one dynamic allocation,
not a transferable reservation for iOS. The current XNU RAM window starts
at4GiB, while the modem's sector-vector buffer address is32-bit. A normal
kernel allocation cannot provide the necessary low address in this setup.
The donor borrows camera memory; this test instead claims ordinary low DRAM
after ABL hands control to the bare-metal shim, outside the RAM advertised
to XNU. No EFI allocator or running Android memory allocator is involved.
The test verifies this ownership and CPU mapping before any modem sharing.

This package is NOT the RMTFS service: it publishes no service14, makes no
SCM calls and does not start MBA/MPSS. It reads only metadata and the first
4096 bytes of each backing partition. Full RAM snapshots and the service
will follow after device evidence confirms this preflight.

## Reservation contract

Opt in when building shim with EQUULEUS_RMTFS_RESERVE=1. Other builds retain
the previous behavior. Only BOARD_EQUULEUS enables this path.
Candidate pool:0xa8000000, total0x20c000. Layout:

| Offset | Size | Use |
| --- | --- | --- |
|0|0x4000|Header page|
|0x4000|0x4000|Lower canary page|
|0x8000|0x200000|Zeroed prospective RMTFS buffer|
|0x208000|0x4000|Upper canary page|

Data PA0xa8008000 is16KiB aligned and below4GiB. It is a candidate selected
from the device's ordinary low DRAM, not Android's observed UIO address.
The bounded FDT17 parser requires root/memory and reserved-memory cell
layout2/2, DRAM containment, no overlap with any reserved-memory reg or the
FDT memory-reserve table. It refuses malformed lengths, offsets, strings,
unterminated maps, unsupported cells and address overflow. Checks also
exclude the live FDT blob, shim code/BSS/stacks, initrd/payload and framebuffer,
and require XNU physBase>=4GiB. A collision stops the boot with a visible
reservation-refused message; it never silently picks another address.
The original equuleus-live.dtb passed this range check on the host.

Shim zeroes the pool, fills canary pages, and records a64-byte versioned
header with fixed layout and checksum. After successful reservation it
appends eqrmtfs_pool=156 to this boot's kernel command line. The preflight
requires that stamp before mapping; a kernel booted with the old shim will
refuse the test, even if old RAM contents remain. The stamp/checksum are
accidental-misconfiguration guards, not protection against a malicious loader.

## Kernel mode11

sweetmss=11 exits through the preflight before MSS survey/power/start code.
It maps the complete pool using the existing Normal-NC io_map convention,
checks header and canaries, verifies the full2MiB buffer is zero, writes and
reads back its first/last words, restores those words to zero and rechecks
canaries. A header, guard or nonzero-buffer mismatch stops before writes.
The one-shot mapping is retained until full reboot; it is not unmapped like
the permanent MMIO mappings that caused earlier panics.

Backing sizes must match the Android audit:
modemst1=8388608, modemst2=8388608, fsg=8388608, fsc=262144 bytes.
The named UFS API reports its resolved LUN and size, then reads one4KiB block
from each into a temporary RAM buffer. Contents are never logged, hashed,
exported, or written back; the temporary buffer is zeroed and freed. No LUN
number is inferred from Android sd device letters. A missing/wrong-size or
unreadable partition produces FAIL. Full RAM shadows are not created yet.

The success marker is `eqrmt: preflight PASS`. It proves this limited CPU
pool/read path, not TrustZone sharing, modem access, protocol correctness,
WLAN UP, Wi-Fi connectivity or resolution of the AXI HALT issue. Other modes
retain0155 behavior. Touch/display geometry is unchanged.

## Validation and next device test

Host tests replay0149..0156 and compile the actual FDT validator and kernel
preflight under ASan/UBSan: DRAM/reserved/memreserve/cell/overflow/truncation,
3000 FDT mutations, runtime-range collision checks, eleven actual pool/map/
partition/read/allocation/stamp scenarios and a board/one-shot mode11 gate.
The kernel and shim contract headers must match byte-for-byte. Previous0155
host service tests also pass. The installer cross-compiles the actual loader
with the user's existing AArch64 compiler and checks ABS64 relocations before
commit/push/dispatch. Full XNU and on-device preflight remain pending.

The package applies shim changes as a checked, idempotent git patch, rather
than replacing whole local files. Build the eventual test image with:
BOARD=equuleus EQUULEUS_XNU_BOOT=1 EQUULEUS_RMTFS_RESERVE=1 and sweetmss=11,
using the existing native ADT. Fully reboot into Android before temporary
fastboot boot. Save the complete persistent log after four minutes, and a
photo if shim refuses the reservation before XNU can log.
