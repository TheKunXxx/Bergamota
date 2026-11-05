# Equuleus WLAN SMMU handoff

## Hardware evidence: 0173 and 0174

CB3 is unreferenced by valid translated streams. SCTLR changed 0xe0 -> 0xe4 -> 0xe0. All six 0174 probes passed and restored (writable_mask=0x3f, restored_mask=0x3f): TTBR0 low/high, TCR, TCR2, MAIR0/1. Final SCTLR=0xe0, FSR=0x400 (format bits), GFSR=0. MSA assignment and CAP succeed; FW_READY remains zero. Direct bypass is rewritten to FAULT by firmware.

## 0175 implementation; kernel CI and hardware pending

Opt-in eqwlan_translate=1 uses CB3 with three 4 KiB tables in a retained 16 KiB kernel allocation. Page-table physical addresses must be aligned and below 40 bits. Only the reserved MSA range 0xa8300000..0xa8400000 is identity mapped, noncacheable, read/write and execute-never. The tables themselves are not mapped for WLAN DMA. This is the initial firmware handshake mapping, not a general WLAN data-buffer mapper.

Before writes: check MSA assignment/ack/layout, known geometry, stage-1 and 4 KiB support, fault status, CB3 snapshot, free stream slot and absence of overlapping SID 0x40/0x41 mappings or another CB3 owner. Recheck ownership before programming and before publishing the stream. Cache cleaning precedes bounded ASID/TLB synchronization. Translation settings and SCTLR are read back. Publish SMR 0x80010040 with S2CR=3 only after those checks. Return route-ready and permit existing rail votes only when the route readback and fault checks pass.

Failures before rail votes unpublish the match before disabling/restoring the context. If match invalidation fails, leave tables/context retained and refuse power. Each rollback reports detached/restored; no allocation is freed even on failure. Active mappings are retained until a full reboot. A once-per-second fault watch reports GFSR, FSR, FAR, FSYNR0 and SID; the final context snapshot is also logged. No BDF download, WLAN mode request or networking stack was added.

Host ASan/UBSan fake-MMIO checks pass for exact 256-page bounds, execute-never attributes, repeated invocation, route/context conflicts, unassigned MSA, allocation/physical bounds failures, register/S2CR/SMR readback failures, TLB timeout, rollback and fault observation. Host tests omit ARM barriers/cache instructions and do not prove hardware behavior. Patch application, helper shell syntax and CI guard upgrade/idempotency checked. CI runs the replay and requires patch 0175 plus source markers.

Build with xnu.yml on port/equuleus, then tools/equuleus-image-0175-msa-translate.sh. Temporary fastboot boot image: equuleus-wlfw-0175-msa-translate.img. Look for translate active, power SMMU_route=1 rails_ok=1, FW_READY indications and translation faults. All hardware outcomes are pending.

References: [Linux v6.12 arm-smmu.h](https://github.com/torvalds/linux/blob/v6.12/drivers/iommu/arm/arm-smmu/arm-smmu.h), [pinned dipper implementation](https://github.com/youzjuzi/dipper-xnu/blob/4e82c709ea42ebb509fa101b52972fdc890b873e/patches/xnu-mi8.patch).
