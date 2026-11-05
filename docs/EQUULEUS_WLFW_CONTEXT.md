# Equuleus WLAN SMMU handoff

## Hardware evidence

0173: unused CB3 SCTLR changed 0xe0 -> 0xe4 -> 0xe0. 0174: all six TTBR0/TCR/TCR2/MAIR probes wrote and restored (masks 0x3f); SCTLR=0xe0, FSR=0x400 (format), GFSR=0. Direct bypass is rewritten to FAULT.

0175: MSA assignment and CAP succeed. Table allocation and translation-register checks reach SCTLR enable. The requested SCTLR=0x1127 reads back 0x127. Exact equality rejects it before stream publication (SMR=0, S2CR=0); rollback reports detached=1/restored=1. No WLAN rail votes occurred; FW_READY=0. This log does not prove working DMA translation.

## 0176 fix; kernel build and hardware pending

ASIDPNE bit 12 is an optional broadcast-TLB hint; the ARM specification permits ignoring it and it does not affect locally initiated TLB invalidations. Request SCTLR=0x127 instead, retaining exact equality for the remaining functional bits. Also program TCR2 and TCR before TTBRs, matching Linux ordering. Regression replay models ignored ASIDPNE and still rejects a missing SCTLR.M; it checks TCR-before-TTBR ordering. Existing bounds, collisions, ignored writes, TLB timeout and rollback replay passes with ASan/UBSan. Helper shell syntax, patch application and CI guard checks pass. These host checks omit ARM cache/barrier instructions and do not replace a device test.

## Retained 0175 implementation

Opt-in eqwlan_translate=1 uses three 4 KiB tables in a retained 16 KiB allocation, with aligned physical addresses below 40 bits. Only MSA 0xa8300000..0xa8400000 is identity mapped, noncacheable, read/write and execute-never. Tables are not mapped for WLAN DMA. This covers the firmware handshake only; there is no general data-buffer mapper, BDF download or WLAN mode request.

MSA assignment/ack/layout, exact geometry, stage-1/4 KiB support, fault state, CB3 snapshot and stream/context ownership are checked before writes. Cache maintenance precedes bounded local ASID/TLB synchronization. Settings and SCTLR are read back before publishing SMR=0x80010040 and S2CR=3. Only a verified route permits the existing rail votes. Failure unpublishes before disabling/restoring CB3; failed invalidation retains context/tables and refuses power. Memory is never freed or reclaimed before full reboot. Active mappings remain until reboot. Fault watch reports GFSR/FSR/FAR/FSYNR0/SID; stop logs the final context snapshot.

Build xnu.yml on port/equuleus, then tools/equuleus-image-0176-sctlr-hint.sh. Temporary fastboot image: equuleus-wlfw-0176-sctlr-hint.img. Inspect translate active, power SMMU_route=1 rails_ok=1, FW_READY indications and translation faults. 0176 hardware outcomes are pending.

References: [ARM SMMUv2 IHI0062D.c sections 1.6.5 and 5.3.2](https://documentation-service.arm.com/static/5f900d34f86e16515cdc08fb), [Linux v6.12 register programming](https://github.com/torvalds/linux/blob/v6.12/drivers/iommu/arm/arm-smmu/arm-smmu.c), [pinned dipper implementation](https://github.com/youzjuzi/dipper-xnu/blob/4e82c709ea42ebb509fa101b52972fdc890b873e/patches/xnu-mi8.patch).
