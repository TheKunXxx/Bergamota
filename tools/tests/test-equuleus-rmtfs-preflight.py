#!/usr/bin/env python3
"""Actual FDT validator, loader cross-compile and kernel preflight fault tests."""
from pathlib import Path
import ctypes,os,struct,subprocess,tempfile
repo=Path(__file__).resolve().parents[2]
def be(v):return struct.pack('>I',v)
def fdt(reserved=False,memreserve=False,base=0x80000000,size=0x80000000,cells=2):
 names=b'#address-cells\0#size-cells\0reg\0';s=bytearray()
 def begin(n):
  s.extend(be(1)+n.encode()+b'\0');s.extend(b'\0'*((-len(s))%4))
 def prop(n,v):
  s.extend(be(3)+be(len(v))+be(names.index(n.encode()+b'\0'))+v);s.extend(b'\0'*((-len(s))%4))
 begin('');prop('#address-cells',be(cells));prop('#size-cells',be(2))
 begin('memory@80000000');prop('reg',struct.pack('>QQ',base,size));s.extend(be(2))
 begin('reserved-memory');prop('#address-cells',be(2));prop('#size-cells',be(2))
 begin('test@a8000000' if reserved else 'framebuffer@9d400000');prop('reg',struct.pack('>QQ',0xa8000000 if reserved else 0x9d400000,0x20c000 if reserved else 0x2400000));s.extend(be(2)*3+be(9))
 r=struct.pack('>QQ',0xa8000000,0x20c000) if memreserve else b'';r+=b'\0'*16
 off=40+len(r);strings=off+len(s);total=strings+len(names)
 return struct.pack('>10I',0xd00dfeed,total,off,strings,40,17,16,0,len(names),len(s))+r+s+names
with tempfile.TemporaryDirectory() as td:
 root=Path(td);c=root/'fdt.c';exe=root/'fdt'
 c.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "equuleus_rmtfs_fdt.h"
int main(int argc,char **argv){assert(argc==3);FILE *f=fopen(argv[1],"rb");assert(f);fseek(f,0,SEEK_END);size_t n=(size_t)ftell(f);rewind(f);uint8_t *b=malloc(n);assert(b && fread(b,1,n,f)==n);fclose(f);assert(eq_rmt_fdt_usable(b,n)==atoi(argv[2]));
 if(atoi(argv[2])){for(size_t i=0;i<n;i++)assert(!eq_rmt_fdt_usable(b,i));uint8_t *q=malloc(n);uint32_t seed=3;for(unsigned i=0;i<3000;i++){memcpy(q,b,n);seed=seed*1664525u+1013904223u;q[seed%n]^=(uint8_t)(1+(seed>>16));(void)eq_rmt_fdt_usable(q,n);}free(q);}
 assert(eq_rmt_overlap(0xfffffffffffffff0ull,32,0,1));
 assert(eq_rmt_boot_ranges_ok(0x81000000,0x83000000,0x85000000,0x80000,0x80080000,0x80100000,0x100000000ull,0xc0000000,0x9d400000,0x2400000));
 assert(!eq_rmt_boot_ranges_ok(EQ_RMT_POOL,EQ_RMT_POOL+0x1000,0x85000000,0x80000,0x80080000,0x80100000,0x100000000ull,0xc0000000,0x9d400000,0x2400000));
 assert(!eq_rmt_boot_ranges_ok(0x81000000,0x83000000,EQ_RMT_POOL,0x80000,0x80080000,0x80100000,0x100000000ull,0xc0000000,0x9d400000,0x2400000));
 assert(!eq_rmt_boot_ranges_ok(0x81000000,0x83000000,0x85000000,0x80000,EQ_RMT_POOL,EQ_RMT_POOL+0x1000,0x100000000ull,0xc0000000,0x9d400000,0x2400000));
 assert(!eq_rmt_boot_ranges_ok(0x81000000,0x83000000,0x85000000,0x80000,0x80080000,0x80100000,0x100000000ull,0xc0000000,EQ_RMT_POOL,0x2400000));
 assert(!eq_rmt_boot_ranges_ok(0x81000000,0x83000000,0x85000000,0x80000,0x80080000,0x80100000,0x80000000,0xc0000000,0x9d400000,0x2400000));
free(b);return 0;}
''')
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(repo/'shim'),str(c),'-o',str(exe)],check=True)
 env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'}
 for i,(blob,ok) in enumerate([(fdt(),1),(fdt(reserved=True),0),(fdt(memreserve=True),0),(fdt(base=0x100000000,size=0x100000000),0),(fdt(cells=1),0),(fdt(base=0xffffffffffff0000,size=0x20000),0)]):
  p=root/('case%u.dtb'%i);p.write_bytes(blob);subprocess.run([str(exe),str(p),str(ok)],check=True,env=env)
 # Replay all stages with a driver-list interior, never just a BOF fixture.
 dev=root/'bsd/dev';dev.mkdir(parents=True);p=dev/'equuleus_mss.c'
 t=(repo/'xnu/patches/0149-equuleus-mss-mba-bringup.patch').read_text().split('+++ b/bsd/dev/equuleus_mss.c\n',1)[1];p.write_text('\n'.join(l[1:] for l in t.splitlines() if l.startswith('+'))+'\n')
 conf=root/'bsd/conf/files';conf.parent.mkdir(parents=True);conf.write_text('prefix\n'*117+'bsd/dev/beryllium_wlan.c\t\tstandard\nbsd/dev/equuleus_mss.c\t\tstandard\nbsd/dev/beryllium_bt_hci.c\t\tstandard\n'+'suffix\n'*12)
 subprocess.run(['git','init','-q',td],check=True)
 for pre in ['0150','0151','0152','0153','0154','0155','0156']:
  patch=next((repo/'xnu/patches').glob(pre+'-*'));subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True);subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
 assert (dev/'equuleus_rmtfs_contract.h').read_bytes()==(repo/'shim/equuleus_rmtfs_contract.h').read_bytes()
 source=p.read_text();actual=source[source.index('/* 0156 preflight:'):source.index('void\nequuleus_mss_probe(void)')]
 assert 'assign_mem(' not in actual and 'ml_io_unmap' not in actual
 harness=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#include "equuleus_rmtfs_contract.h"
typedef uintptr_t vm_offset_t;
#define PAGE_SIZE 16384u
#define VM_WIMG_WCOMB 1
#define VM_PROT_READ 1
#define VM_PROT_WRITE 2
#define Z_WAITOK 1
#define Z_ZERO 2
static unsigned scenario,maps,read_calls,size_calls,allocations,passes;
static uint8_t *memory;
static bool PE_parse_boot_argn(const char *name,void *out,size_t n){assert(!strcmp(name,"eqrmtfs_pool") && n==sizeof(unsigned));*(unsigned *)out=156;return scenario!=10;}
static void say(const char *s,...){if(strstr(s,"preflight %s")){va_list ap;va_start(ap,s);passes+=!strcmp(va_arg(ap,const char *),"PASS");va_end(ap);}}
static void settle(void){}
static void *kalloc_data(size_t n,unsigned f){assert(n==4096 && f==3);if(scenario==7)return NULL;allocations++;return calloc(1,n);}
static void kfree_data(void *p,size_t n){assert(n==4096 && allocations);for(unsigned i=0;i<n;i++)assert(((uint8_t *)p)[i]==0);allocations--;free(p);}
static vm_offset_t io_map(uint64_t p,uint64_t n,unsigned attr,unsigned prot,bool can_unmap){assert(p==EQ_RMT_POOL && n==EQ_RMT_SPAN && !(p%PAGE_SIZE) && !(n%PAGE_SIZE) && attr==1 && prot==3 && can_unmap);maps++;return scenario==4?0:(uintptr_t)memory;}
static const char *const parts[]={"modemst1","modemst2","fsg","fsc"};
static int sweet_ufs_part_size(const char *name,uint8_t *lun,uint64_t *size){assert(size_calls<4 && !strcmp(name,parts[size_calls]));*lun=(uint8_t)(size_calls+1);*size=size_calls==3?0x40000:0x800000;size_calls++;if(scenario==5)*size=0x1000;return scenario==8?2:0;}
static int sweet_ufs_read_part(const char *name,uint64_t off,void *dst,uint64_t n){assert(read_calls<4 && !strcmp(name,parts[read_calls]) && off==0 && n==4096);read_calls++;memset(dst,0x5a,n);return scenario==6 || (scenario==9 && read_calls==4)?5:0;}
'''
 main=r'''
int main(int argc,char **argv){assert(argc==2);scenario=(unsigned)atoi(argv[1]);memory=calloc(1,EQ_RMT_SPAN);assert(memory);struct eq_rmt_contract c={EQ_RMT_MAGIC,1,EQ_RMT_POOL,EQ_RMT_SPAN,EQ_RMT_DATA,EQ_RMT_BYTES,EQ_RMT_GUARD,0};c.checksum=eq_rmt_checksum(&c);memcpy(memory,&c,sizeof(c));
 uint64_t *pool=(uint64_t *)memory;for(unsigned i=0;i<EQ_RMT_PAGE/8;i++)pool[EQ_RMT_PAGE/8+i]=pool[(2*EQ_RMT_PAGE+EQ_RMT_BYTES)/8+i]=EQ_RMT_GUARD;
 if(scenario==1)pool[0]^=1;if(scenario==2)pool[EQ_RMT_PAGE/8]=0;if(scenario==3)pool[2*EQ_RMT_PAGE/8]=1;
 equuleus_rmtfs_preflight();assert(maps==(scenario==10?0u:1u) && allocations==0);
 if(scenario>=1 && scenario<=4)assert(size_calls==0 && read_calls==0);
 if(scenario==0)assert(size_calls==4 && read_calls==4 && passes==1);
 if(scenario)assert(!passes);
 if(scenario==5 || scenario==8)assert(size_calls==1 && read_calls==0);
 if(scenario==6)assert(size_calls==1 && read_calls==1);
 if(scenario==7 || scenario==10)assert(size_calls==0);
 if(scenario==9)assert(size_calls==4 && read_calls==4);
 if(scenario>=5 || scenario==0){for(unsigned i=0;i<EQ_RMT_BYTES/8;i++)assert(pool[2*EQ_RMT_PAGE/8+i]==0);assert(eq_rmt_guards(pool));}
 free(memory);return 0;}
'''
 c.write_text(harness+actual+main)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-I',str(dev),str(c),'-o',str(exe)],check=True)
 for scenario in range(11):subprocess.run([str(exe),str(scenario)],check=True,env=env)
 # Actual entry gate: preflight never reaches MSS survey/power/start routines.
 gate=source[source.index('void\nequuleus_mss_probe(void)'):].split('#endif',1)[0]
 c.write_text(r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
static unsigned mode=11,pre;static bool board=true,mss_halt_all,mss_full_test,mss_glink_test,mss_servreg_test,mss_hostsvc_test;
static bool sweet_board_is(const char *s){(void)s;return board;}
static bool PE_parse_boot_argn(const char *s,void *v,size_t n){(void)s;memcpy(v,&mode,n);return true;}
static void say(const char *s,...){(void)s;}
static void equuleus_rmtfs_preflight(void){pre++;}
static void mss_w2a(void){abort();}static void mss_w2bc(unsigned n){(void)n;abort();}static void mss_run_mba(void){abort();}
'''+gate+r'''
int main(void){board=false;equuleus_mss_probe();assert(!pre);board=true;equuleus_mss_probe();equuleus_mss_probe();assert(pre==1);return 0;}
''')
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
 print('0156 replay, FDT reservations/cell layouts/overflow/truncations/3000 mutations, 11 actual kernel pool/partition failure cases and preflight-only board/one-shot gate passed')
