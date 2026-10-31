#!/usr/bin/env python3
"""Exercise the actual MBA routine from patch 0149 with mocked hardware.

This checks error cleanup, not real register semantics or XNU integration.
"""
from pathlib import Path
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[2]
patch = (repo / 'xnu/patches/0149-equuleus-mss-mba-bringup.patch').read_text()
new = patch.split('+++ b/bsd/dev/equuleus_mss.c\n', 1)[1]
source = '\n'.join(line[1:] for line in new.splitlines() if line.startswith('+'))
body = source.split('static void\nmss_run_mba(void)\n', 1)[1].split('\n/* Called on the existing', 1)[0]
body = 'static void\nmss_run_mba(void)\n' + body
harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
typedef uintptr_t vm_offset_t;
#define MSS_CLOCKS 7
#define VMID_HLOS 3
#define VMID_MSS_MSA 15
#define MBA_MEMORY 0x96900000u
#define MBA_SIZE 0x200000u
#define MPSS_MEMORY 0x8e400000u
#define MPSS_SIZE 0x7800000u
#define VM_WIMG_WCOMB 1
#define VM_PROT_READ 1
#define VM_PROT_WRITE 2
#define RMB_PHYS 0x4180000u
#define PDC_PHYS 0xb2e0000u
#define AOSS_CC_PHYS 0xc2b0000u
#define QDSP6SS_PHYS 0x4080000u
#define TCSR_HALT_PHYS 0x1f60000u
#define QDSP6SS_SLEEP 0x3c
#define QDSP6SS_BOOT_CORE_START 0x400
#define QDSP6SS_BOOT_CMD 0x404
#define Q6SS_CBCR_CLKEN 1u
#define Q6SS_CBCR_CLKOFF (1u<<31)
#define RMB_MSS_STATUS 0x40
#define RMB_PBL_STATUS 4
#define RMB_MBA_STATUS 12
#define NSEC_PER_USEC 1000
#define NSEC_PER_MSEC 1000000
static int scenario, allocations, maps, unmaps, assignments, q6_boots, halted;
static bool sleep_enabled, image_unmapped;
#define say(...) ((void)0)
#define announce(...) ((void)0)
static void *fs_slurp(const char *name, uint32_t *size) {
    assert(!strcmp(name,"image/mba.mbn"));
    if (scenario==1) return NULL;
    *size=scenario==2 ? MBA_SIZE+1 : 16;
    void *p=malloc(*size); assert(p); memset(p,0x55,*size); allocations++; return p;
}
static void kfree_data(void *p, size_t n) { (void)n; free(p); allocations--; }
static vm_offset_t io_map(uint64_t p, size_t n, unsigned f, unsigned prot, bool temporary) {
    assert(p==MBA_MEMORY && n==MBA_SIZE && f==VM_WIMG_WCOMB && temporary);
    (void)prot;
    if (scenario==3) return 0;
    maps++; return (vm_offset_t)calloc(1,n);
}
static void ml_io_unmap(vm_offset_t p,size_t n) {
    assert(n==MBA_SIZE);free((void *)p);unmaps++;image_unmapped=true;
}
static vm_offset_t ml_io_map(vm_offset_t p,size_t n) {(void)n;return p;}
static void settle(void) {}
static bool qmp_send(const char *s) {(void)s;return scenario!=4;}
static bool rpmh_level_pos(const char *s,uint32_t n) {(void)s;(void)n;return scenario!=5;}
static bool mss_clocks_on(unsigned a,unsigned b,bool *turned) {
    (void)a;(void)b;(void)turned;return scenario!=6;
}
static void mss_clocks_off(unsigned a,unsigned b,const bool *turned) {(void)a;(void)b;(void)turned;}
static void mss_reset_deassert(vm_offset_t a,vm_offset_t b,vm_offset_t c) {(void)a;(void)b;(void)c;}
static void mss_reset_assert(vm_offset_t a,vm_offset_t b) {(void)a;(void)b;}
static bool assign_mem(const char *name,uint32_t p,uint32_t size,uint64_t *owners,bool local,bool remote) {
    (void)name;(void)size;
    assert(image_unmapped);
    assert(p==MBA_MEMORY || p==MPSS_MEMORY);
    assignments++;
    if (scenario==7 && remote) return false;
    *owners=(local?(1ull<<VMID_HLOS):0)|(remote?(1ull<<VMID_MSS_MSA):0); return true;
}
static uint32_t rd(vm_offset_t a) {
    if (a==QDSP6SS_PHYS+QDSP6SS_SLEEP) return scenario==8 ? Q6SS_CBCR_CLKOFF : (sleep_enabled?1:0);
    if (a==RMB_PHYS+RMB_MSS_STATUS) return scenario==9 ? 0 : 1;
    if (a==RMB_PHYS+RMB_PBL_STATUS) return scenario==10 ? 2 : 1;
    if (a==RMB_PHYS+RMB_MBA_STATUS) return scenario==11 ? (uint32_t)-1 : 1;
    return 0;
}
static void wr(vm_offset_t a,uint32_t v) {
    (void)v;
    if (a==QDSP6SS_PHYS+QDSP6SS_SLEEP) sleep_enabled=true;
    if (a==QDSP6SS_PHYS+QDSP6SS_BOOT_CORE_START) q6_boots++;
}
static void delay_for_interval(unsigned n,unsigned scale) {(void)n;(void)scale;}
static bool halt_port(const char *name,vm_offset_t a) {(void)name;(void)a;halted++;return scenario!=12;}
static void gcc_show(void) {}
static int rail_position(const char *n,uint32_t l,uint32_t *a,bool show) {(void)n;(void)l;(void)show;*a=1;return 0;}
'''
main = r'''
int main(int argc,char **argv) {
    assert(argc==2); scenario=atoi(argv[1]);mss_run_mba();
    assert(allocations==0);assert(maps==unmaps);
    if(scenario<=6) {
        if(scenario==0) {assert(q6_boots==1);assert(assignments==4);assert(halted==3);}
        else {assert(q6_boots==0);assert(assignments==0);}
    }
    if(scenario==7) assert(q6_boots==0);
    if(scenario==8) assert(q6_boots==0 && assignments==4);
    if(scenario>=9 && scenario<=11) assert(assignments==4 && halted==3);
    if(scenario==12) assert(assignments==2 && halted==3);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='eqmss-host-') as tmp:
    c=Path(tmp)/'mba.c';exe=Path(tmp)/'mba'
    c.write_text(harness+'\n'+body+'\n'+main)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',
                    '-Wno-unused-but-set-variable','-Wno-unused-variable',
                    '-fsanitize=undefined',str(c),'-o',str(exe)],check=True)
    for n in range(13):
        subprocess.run([str(exe),str(n)],check=True)
print('13 MBA success/failure and cleanup cases passed (mock hardware)')
