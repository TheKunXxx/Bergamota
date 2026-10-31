#!/usr/bin/env python3
"""Replay 0149->0150->0151 and execute actual HALT routine with mocked MMIO."""
from pathlib import Path
import subprocess
import tempfile
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    patch=(repo/'xnu/patches/0149-equuleus-mss-mba-bringup.patch').read_text()
    tail=patch.split('+++ b/bsd/dev/equuleus_mss.c\n',1)[1]
    path=root/'bsd/dev/equuleus_mss.c';path.parent.mkdir(parents=True)
    path.write_text('\n'.join(s[1:] for s in tail.splitlines() if s.startswith('+'))+'\n')
    subprocess.run(['git','init','-q',str(root)],check=True)
    for name in ('0150-equuleus-mpss-smp2p-bringup.patch','0151-equuleus-mpss-stop-diagnostics.patch'):
        p=repo/'xnu/patches'/name
        subprocess.run(['git','apply','--check',str(p)],cwd=root,check=True)
        subprocess.run(['git','apply',str(p)],cwd=root,check=True)
    source=path.read_text()
    halt=source[source.index('static bool\nhalt_port('):source.index('/* 0150 MPSS')]
    harness=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
typedef uintptr_t vm_offset_t;
#define NSEC_PER_MSEC 1000000
static unsigned mode,ticks,writes,cleared; static uint32_t req;
static void say(const char *s,...) {(void)s;}
static void settle(void) {}
static void delay_for_interval(unsigned n,unsigned u) {(void)n;(void)u;ticks++;}
static uint32_t rd(vm_offset_t a) {
 if(a==0x1000)return mode==5?0:req;
 if(a==0x1004)return (mode==1 || mode==4)?1:(mode==2 && ticks>=3);
 assert(a==0x1008);
 if(mode==0)return 1;
 if(mode==1)return req && !cleared;
 if(mode==2)return ticks>=3;
 if(mode==6)return cleared;
 return 0;
}
static void wr(vm_offset_t a,uint32_t v) {assert(a==0x1000);req=v;writes++;if(!v)cleared++;}
'''
    main=r'''
int main(void) {
 for(mode=0;mode<7;mode++) {
  ticks=writes=cleared=req=0;
  bool ok=halt_port("modem",0x1000);
  assert(ok==(mode==0 || mode==1 || mode==2));
  if(mode==0)assert(writes==0 && ticks==0);
  else assert(writes==2 && req==0 && cleared==1 && ticks<=1000);
  if(mode==1)assert(ok && cleared && rd(0x1008)==0);
  if(mode==6)assert(!ok && rd(0x1008)==1);
 }
 return 0;
}
'''
    c=root/'halt.c';c.write_text(harness+halt+main);exe=root/'halt'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
    # Failure remains fail-closed before either SCM reclaim call.
    boot=source.split('static void\nmss_run_mba(void)',1)[1]
    guard=boot.index('if (!halted)')
    reclaim=boot.index('assign_mem("mba", MBA_MEMORY, MBA_SIZE, &mba_owners, true, false)')
    assert guard<reclaim and 'return;' in boot[guard:reclaim]
    for phase in ('before-stop','after-stop','before-halt','after-halt','after-reset'):
        assert f'equuleus_mss_stop_snapshot("{phase}")' in source
    assert 'after-clocks-off' not in source
    print('0151 patch replay and 7 actual HALT MMIO scenarios passed; reclaim guard retained')
    snapshot=source[source.index('void\nequuleus_mss_stop_snapshot('):source.index('/* Linux samples IDLE')]
    snap_harness=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
typedef uintptr_t vm_offset_t;
#define PAGE_SIZE 16384u
#define TCSR_HALT_PHYS 0x01f60000ul
#define RMB_PHYS 0x04000000ul
#define PDC_PHYS 0x0b200000ul
#define AOSS_CC_PHYS 0x0c2b0000ul
#define RMB_MBA_STATUS 0x0c
#define RMB_MSS_STATUS 0x40
#define RMB_ALT_RESET 0x44
#define PDC_SYNC_RESET 0x100
static unsigned maps,unmaps,rmb_reads,clock_reads,fail_map;
static void say(const char *s,...) {(void)s;}
static void gcc_show(void) {clock_reads++;}
static vm_offset_t ml_io_map(uintptr_t p,unsigned n) {assert(n && n%PAGE_SIZE==0 && p%PAGE_SIZE==0);maps++;return maps==fail_map?0:p;}
static uint32_t rd(vm_offset_t a) {if(a>=RMB_PHYS && a<RMB_PHYS+4096)rmb_reads++;return 0;}
'''
    snap_main=r'''
int main(int argc,char **argv) {
 assert(argc==3);
 unsigned p=(unsigned)atoi(argv[1]);fail_map=(unsigned)atoi(argv[2]);
 assert(p<5 && fail_map<=4);
 const char *phases[]={"before-stop","after-stop","before-halt","after-halt","after-reset"};
 equuleus_mss_stop_snapshot(phases[p]);
 assert(maps==4 && unmaps==0 && clock_reads==1);
 if(p==4 || fail_map==2 || fail_map==3 || fail_map==4)assert(rmb_reads==0);
 else assert(rmb_reads==3);
 equuleus_mss_stop_snapshot(phases[p]);
 assert(maps==(fail_map?5u:4u) && unmaps==0 && clock_reads==2);
 equuleus_mss_stop_snapshot(phases[p]);
 assert(maps==(fail_map?5u:4u) && unmaps==0 && clock_reads==3);
 return 0;
}
'''
    c.write_text(snap_harness+snapshot+snap_main)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(c),'-o',str(exe)],check=True)
    for phase in range(5):
        for failed in range(5):
            subprocess.run([str(exe),str(phase),str(failed)],check=True)
    print('25 snapshot cases passed: permanent mappings cached, failed maps retried, zero unmap calls')
