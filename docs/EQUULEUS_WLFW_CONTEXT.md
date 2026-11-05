# Equuleus WLAN context handoff

0173 hardware: CB3 SCTLR changed 0xe0 -> 0xe4 -> 0xe0, writable=1 and restored_ok=1. Direct bypass is still rewritten to FAULT. MSA/CAP succeed; FW_READY=0.

0174 pending hardware: eqwlan_cbconfig=1 tests TTBR0 low/high, TCR, TCR2, MAIR0/1 while translation stays disabled. Each register is restored before the next. Stream references and context state are rechecked before each write; failed restoration stops the sequence. Complete success masks: writable_mask=0x3f, restored_mask=0x3f. Inspect SCTLR, FSR and GFSR as well.

Host fake-MMIO tests cover accepted/ignored writes, occupied context refusal and stopping after failed restore. Full kernel compilation and phone results remain pending. Register offsets follow Linux v6.12 drivers/iommu/arm/arm-smmu/arm-smmu.h. No translation tables or stream attachment are introduced here.
