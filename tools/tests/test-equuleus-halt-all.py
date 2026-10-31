#!/usr/bin/env python3
"""Replay complete MSS patch chain; execute actual 0152 HALT code with mocked MMIO."""
from pathlib import Path
import subprocess,tempfile
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as td:
 root=Path(td);p=root/'bsd/dev/equuleus_mss.c';p.parent.mkdir(parents=True)
 tail=(repo/'xnu/patches/0149-equuleus-mss-mba-bringup.patch').read_text().split('+++ b/bsd/dev/equuleus_mss.c\n',1)[1]
 p.write_text('\n'.join(l[1:] for l in tail.splitlines() if l.startswith('+'))+'\n')
 subprocess.run(['git','init','-q',td],check=True)
 for name in ['0150-equuleus-mpss-smp2p-bringup.patch','0151-equuleus-mpss-stop-diagnostics.patch','0152-equuleus-explicit-axi-halt.patch']:
  patch=repo/'xnu/patches'/name
  subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
  subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
 source=p.read_text()
 flags=source[source.index('static bool mss_halt_all;'):source.index('/* Linux samples IDLE')]
 halt=source[source.index('static bool\nhalt_port('):source.index('/* 0150 MPSS')]
 harness=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
typedef uintptr_t vm_offset_t;
#define NSEC_PER_MSEC 1000000
static unsigned scenario,ticks,writes;static uint32_t request;
static void say(const char *s,...) {(void)s;}
static void settle(void) {}
static void delay_for_interval(unsigned n,unsigned u) {(void)n;(void)u;ticks++;}
static uint32_t rd(vm_offset_t a) {
 if(a==0x1000)return scenario==4?0:request;
 if(a==0x1004)return (scenario==0 || scenario==6)?(request && ticks>=3):(scenario==2);
 assert(a==0x1008);
 switch(scenario) {
 case 0:case 1:case 4:return 1;
 case 2:case 3:return 0;
 case 5:return writes>=2;
 case 6:return request && ticks>=3;
 default:assert(0);return 0;
 }
}
static void wr(vm_offset_t a,uint32_t v) {assert(a==0x1000);request=v;writes++;}
'''
 main=r'''
int main(void) {
 for(unsigned strict=0;strict<2;strict++)for(scenario=0;scenario<7;scenario++) {
  ticks=writes=request=0;mss_halt_all=strict;
  bool ok=halt_port("test",0x1000);
  bool expected=strict?(scenario==0 || scenario==6):(scenario==0 || scenario==1 || scenario==4 || scenario==6);
  assert(ok==expected && request==0 && ticks<=1000);
  if(!strict && (scenario==0 || scenario==1 || scenario==4))assert(writes==0);
  else assert(writes==2);
 }
 return 0;
}
'''
 c=root/'test.c';exe=root/'test';c.write_text(harness+flags+halt+main)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
 assert 'mss_halt_all = mode == 7;' in source
 assert 'mss_full_test = mode == 6 || mode == 7;' in source
 boot=source.split('static void\nmss_run_mba(void)',1)[1]
 assert boot.index('if (!halted)') < boot.index('assign_mem("mba", MBA_MEMORY, MBA_SIZE, &mba_owners, true, false)')
 assert 'ml_io_unmap' not in source[source.index('void\nequuleus_mss_stop_snapshot('):source.index('/* 0152:')]
 print('0152 full patch replay and 14 actual HALT scenarios passed; mode7 gate and no-reclaim guard retained')
