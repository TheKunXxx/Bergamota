/*
 * Milestone 4: act as iBoot for xnu.
 *
 * mkpayload.py already resolved the kernel's chained fixups and built the
 * ADT, so this only has to: find the payload in the ABL ramdisk, copy the
 * segments to phys_base + (vmaddr - virt_base), place the ADT and
 * boot_args behind the kernel, and jump to the entry point with the MMU
 * and caches off, x0 = boot_args (physical).
 */
#include <stdint.h>
#include "console.h"
#include "fdt.h"
#include "loader.h"
#if defined(BOARD_EQUULEUS) && defined(EQUULEUS_RMTFS_RESERVE)
#include "equuleus_rmtfs_fdt.h"
extern char _head[], _end[];
#endif

#define BOOT_LINE_LENGTH	608
#define PAGE_16K		0x4000UL

struct payload_seg {
	uint64_t vmaddr, vmsize, file_off, file_size;
};

struct payload {
	char magic[8];
	uint32_t version, nsegs;
	uint64_t virt_base, entry_va, adt_off, adt_size, kernel_end;
	uint64_t phys_base, mem_size;
	char cmdline[BOOT_LINE_LENGTH];
	struct payload_seg segs[];
};

/* pexpert/pexpert/arm64/boot.h, Revision/Version 2 */
struct boot_video {
	uint64_t v_baseAddr, v_display, v_rowBytes, v_width, v_height, v_depth;
};

struct boot_args {
	uint16_t Revision, Version;
	uint64_t virtBase, physBase, memSize, topOfKernelData;
	struct boot_video Video;
	uint32_t machineType;
	uint64_t deviceTreeP;
	uint32_t deviceTreeLength;
	char CommandLine[BOOT_LINE_LENGTH];
	uint64_t bootFlags, memSizeActual;
};

_Static_assert(__builtin_offsetof(struct payload, segs) == 0x2a8, "payload header layout");
_Static_assert(__builtin_offsetof(struct boot_args, Video) == 40, "boot_args layout");
_Static_assert(__builtin_offsetof(struct boot_args, CommandLine) == 108, "boot_args layout");
_Static_assert(sizeof(struct boot_args) == 736, "boot_args layout");

/* MMU off: everything is Device memory, so copy in aligned 8-byte words. */
static void copy64(uintptr_t dst, uintptr_t src, uint64_t n)
{
	volatile uint64_t *d = (volatile uint64_t *)dst;
	volatile const uint64_t *s = (volatile const uint64_t *)src;
	for (uint64_t i = 0; i < (n + 7) / 8; i++)
		d[i] = s[i];
}

static void zero64(uintptr_t dst, uint64_t n)
{
	volatile uint64_t *d = (volatile uint64_t *)dst;
	for (uint64_t i = 0; i < n / 8; i++)
		d[i] = 0;
}

static int magic_ok(const char *m)
{
	static const char want[] = "SWEETXNU";
	for (int i = 0; i < 8; i++)
		if (m[i] != want[i])
			return 0;
	return 1;
}

typedef void (*xnu_entry_t)(uint64_t boot_args_pa);

const char *loader_boot(uintptr_t dtb)
{
	uint64_t rd_start, rd_end;

	if (!fdt_chosen_u64(dtb, "linux,initrd-start", &rd_start) ||
	    !fdt_chosen_u64(dtb, "linux,initrd-end", &rd_end))
		return "no initrd in /chosen";
	con_hex2("INITRD", "lo=", rd_start, "hi=", rd_end);

	const struct payload *p = (const struct payload *)rd_start;
	if (!magic_ok(p->magic))
		return "no SWEETXNU payload";
	if (p->version != 1 || (p->adt_off & 7) || (rd_start & 7))
		return "bad payload header";

	uint64_t pa_of_va_base = p->phys_base - p->virt_base;	/* pa = va + this */
	con_hex2("PHYS", "base=", p->phys_base, "size=", p->mem_size);
	con_hex("VIRT", p->virt_base);
	con_hex("ENTRY", p->entry_va);

	/* The payload must not overlap where the kernel goes. */
	if (rd_end > p->phys_base && rd_start < p->phys_base + p->mem_size)
		return "ramdisk overlaps kernel memory";

#if defined(BOARD_EQUULEUS) && defined(EQUULEUS_RMTFS_RESERVE)
 /* ABL has transferred control; no allocator runs below the XNU RAM window.
  * Claim only ordinary DRAM outside all live FDT and runtime reservations. */
 uint64_t dt_size = (uint64_t)eq_be32((const uint8_t *)dtb + 4);
 if (!eq_rmt_boot_ranges_ok(rd_start,rd_end,dtb,dt_size,(uintptr_t)_head,(uintptr_t)_end,
       p->phys_base,p->mem_size,FB_BASE,(uint64_t)FB_STRIDE*FB_H) ||
     !eq_rmt_fdt_usable((const uint8_t *)dtb,dt_size))
  return "RMTFS pool reservation refused";
 /* Diagnostic only: leave the candidate untouched until the MSA stage. */
 const uint64_t msa_base = 0xa8300000ull, msa_size = 0x100000ull;
 const int msa_ranges_ok =
     !eq_rmt_overlap(msa_base,msa_size,EQ_RMT_POOL,EQ_RMT_SPAN) &&
     !eq_rmt_overlap(msa_base,msa_size,rd_start,rd_end-rd_start) &&
     !eq_rmt_overlap(msa_base,msa_size,dtb,dt_size) &&
     !eq_rmt_overlap(msa_base,msa_size,(uintptr_t)_head,(uintptr_t)_end-(uintptr_t)_head) &&
     !eq_rmt_overlap(msa_base,msa_size,p->phys_base,p->mem_size) &&
     !eq_rmt_overlap(msa_base,msa_size,FB_BASE,(uint64_t)FB_STRIDE*FB_H) &&
     eq_fdt_range_usable((const uint8_t *)dtb,dt_size,msa_base,msa_size);
 zero64(EQ_RMT_POOL,EQ_RMT_SPAN);
 volatile uint64_t *guard_lo=(volatile uint64_t *)(EQ_RMT_POOL+EQ_RMT_PAGE);
 volatile uint64_t *guard_hi=(volatile uint64_t *)(EQ_RMT_DATA+EQ_RMT_BYTES);
 for(uint64_t i=0;i<EQ_RMT_PAGE/8;i++)guard_lo[i]=guard_hi[i]=EQ_RMT_GUARD;
 /* Direct volatile stores avoid compiler-generated memcpy. */
 volatile struct eq_rmt_contract *contract=(volatile struct eq_rmt_contract *)EQ_RMT_POOL;
 contract->version=1;
 contract->pool=EQ_RMT_POOL;
 contract->span=EQ_RMT_SPAN;
 contract->data=EQ_RMT_DATA;
 contract->bytes=EQ_RMT_BYTES;
 contract->guard=EQ_RMT_GUARD;
 contract->checksum=EQ_RMT_MAGIC ^ 1ull ^ EQ_RMT_POOL ^ EQ_RMT_SPAN ^ EQ_RMT_DATA ^ EQ_RMT_BYTES ^ EQ_RMT_GUARD;
 __asm__ volatile("dsb sy" ::: "memory");
 contract->magic=EQ_RMT_MAGIC;
 __asm__ volatile("dsb sy" ::: "memory");
 con_hex2("RMTFS","data=",(uint32_t)EQ_RMT_DATA,"size=",(uint32_t)EQ_RMT_BYTES);
#endif

	for (uint32_t i = 0; i < p->nsegs; i++) {
		const struct payload_seg *s = &p->segs[i];
		uintptr_t dst = s->vmaddr + pa_of_va_base;
		copy64(dst, rd_start + s->file_off, s->file_size);
		if (s->vmsize > s->file_size)
			zero64(dst + ((s->file_size + 7) & ~7UL), s->vmsize - ((s->file_size + 7) & ~7UL));
	}
	con_hex2("SEGS", "n=", p->nsegs, "end=", p->kernel_end + pa_of_va_base);

	/* ADT, then boot_args, behind the kernel; everything below topOfKernelData is ours. */
	uintptr_t adt_pa = p->kernel_end + pa_of_va_base;
	copy64(adt_pa, rd_start + p->adt_off, p->adt_size);
	uintptr_t ba_pa = (adt_pa + p->adt_size + PAGE_16K - 1) & ~(PAGE_16K - 1);
	uintptr_t top = ba_pa + PAGE_16K;

	zero64(ba_pa, PAGE_16K);
	volatile struct boot_args *ba = (volatile struct boot_args *)ba_pa;
	ba->Revision = 2;
	ba->Version = 2;
	ba->virtBase = p->virt_base;
	ba->physBase = p->phys_base;
	ba->memSize = p->mem_size;
	ba->topOfKernelData = top;
	ba->Video.v_baseAddr = FB_BASE;
	ba->Video.v_display = 1;
	ba->Video.v_rowBytes = FB_STRIDE;
	ba->Video.v_width = FB_W;
	ba->Video.v_height = FB_H;
	ba->Video.v_depth = 32;
	ba->deviceTreeP = adt_pa - pa_of_va_base;	/* xnu reads it with the MMU on: a VA */
	ba->deviceTreeLength = (uint32_t)p->adt_size;
	for (int i = 0; i < BOOT_LINE_LENGTH; i++)
		ba->CommandLine[i] = p->cmdline[i];
#if defined(BOARD_EQUULEUS) && defined(EQUULEUS_RMTFS_RESERVE)
 /* Stamp only this boot's validated reservation; old shim boots lack it. */
 const char stamp[] = " eqrmtfs_pool=156";
 unsigned used=0;
 while(used<BOOT_LINE_LENGTH && ba->CommandLine[used])used++;
 if(used+sizeof(stamp)>BOOT_LINE_LENGTH)return "no room for RMTFS reservation stamp";
 for(unsigned i=0;i<sizeof(stamp);i++)ba->CommandLine[used+i]=stamp[i];
 used += sizeof(stamp)-1;
 /* This low-RAM window lies below the kernel's handed-off RAM aperture.
  * Leave it CPU-owned for the metadata-only MSA_INFO stage. */
 const char msa_ok[] = " eqmsa_preflight=1 eqmsa_reserved=166";
 const char msa_no[] = " eqmsa_preflight=0";
 const char *msa_report = msa_ranges_ok ? msa_ok : msa_no;
 unsigned msa_len = msa_ranges_ok ? sizeof(msa_ok) : sizeof(msa_no);
 if (used+msa_len<=BOOT_LINE_LENGTH)
  for(unsigned i=0;i<msa_len;i++)ba->CommandLine[used+i]=msa_report[i];
#endif
	ba->memSizeActual = p->mem_size;
	con_hex2("BOOTARG", "pa=", ba_pa, "top=", top);

	uintptr_t entry_pa = p->entry_va + pa_of_va_base;
	con_hex("JUMP", entry_pa);
	con_str("XNU", "jumping (fbcon clears screen)");

	/* Everything was written with the MMU and caches off; drop any stale I-cache lines too. */
	__asm__ volatile("dsb sy; ic iallu; dsb sy; isb" ::: "memory");
	((xnu_entry_t)entry_pa)(ba_pa);
	return "xnu returned";
}
