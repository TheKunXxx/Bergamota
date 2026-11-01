#!/usr/bin/env python3
"""Replay MSS+GLINK patches; test donor transport and bounded equuleus MMIO adapter."""
from pathlib import Path
import subprocess,tempfile,os
repo=Path(__file__).resolve().parents[2]
wlfw_register=bool(os.environ.get('EQUULEUS_TEST_0164'))
wlfw_cap=wlfw_register or bool(os.environ.get('EQUULEUS_TEST_0163'))
probe_progress=wlfw_cap or bool(os.environ.get('EQUULEUS_TEST_0162'))
deep_mcfg=probe_progress or bool(os.environ.get('EQUULEUS_TEST_0161'))
firmware_paths=deep_mcfg or bool(os.environ.get('EQUULEUS_TEST_0160'))
tftp_replace=firmware_paths or bool(os.environ.get('EQUULEUS_TEST_0159'))
tftp_ram=tftp_replace or bool(os.environ.get('EQUULEUS_TEST_0158'))
rmtfs=tftp_ram or bool(os.environ.get('EQUULEUS_TEST_0157'))
hostsvc=rmtfs or bool(os.environ.get('EQUULEUS_TEST_0155'))
servreg=hostsvc or bool(os.environ.get('EQUULEUS_TEST_0154'))
with tempfile.TemporaryDirectory() as td:
 root=Path(td);p=root/'bsd/dev/equuleus_mss.c';p.parent.mkdir(parents=True)
 tail=(repo/'xnu/patches/0149-equuleus-mss-mba-bringup.patch').read_text().split('+++ b/bsd/dev/equuleus_mss.c\n',1)[1]
 p.write_text('\n'.join(l[1:] for l in tail.splitlines() if l.startswith('+'))+'\n')
 conf=root/'bsd/conf/files';conf.parent.mkdir(parents=True)
 conf.write_text(''.join('fixture/prefix%u.c\tstandard\n' % i for i in range(117))+'bsd/dev/beryllium_wlan.c\t\tstandard\nbsd/dev/equuleus_mss.c\t\tstandard\nbsd/dev/beryllium_bt_hci.c\t\tstandard\n'+''.join('fixture/suffix%u.c\tstandard\n' % i for i in range(12)))
 subprocess.run(['git','init','-q',td],check=True)
 for prefix in ['0150','0151','0152','0153']+(['0154'] if servreg else [])+(['0155'] if hostsvc else [])+(['0156','0157'] if rmtfs else [])+(['0158'] if tftp_ram else [])+(['0159'] if tftp_replace else [])+(['0160'] if firmware_paths else [])+(['0161'] if deep_mcfg else [])+(['0162'] if probe_progress else [])+(['0163'] if wlfw_cap else [])+(['0164'] if wlfw_register else []):
  patch=next((repo/'xnu/patches').glob(prefix+'-*'))
  subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
  subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
 source=p.read_text(); dev=p.parent
 harness=r'''
#define MI8_GLINK_HOST_TEST
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned allocs;
static void *test_alloc(size_t n) {void *p=calloc(1,n);if(p)allocs++;return p;}
static void test_free(void *p) {if(p){assert(allocs);allocs--;free(p);}}
#define MI8_ALLOC(n) test_alloc(n)
#define MI8_FREE(p,n) test_free(p)
#include "equuleus_glink.c"
static uint8_t mem[65536];static uint64_t clock_us;static unsigned rings;
static bool item(void *c,uint32_t i,uint32_t *o,uint32_t *n) {
 (void)c;if(i<478 || i>480)return false;
 *o=i==478?0x1000:i==479?0x2000:0x4000;*n=i==478?32:4096;return true;
}
static void load(void *c,uint32_t o,void *v,uint32_t n) {(void)c;assert((uint64_t)o+n<=sizeof(mem));memcpy(v,mem+o,n);}
static void store(void *c,uint32_t o,uint32_t v) {(void)c;assert(o==0x1004 || o==0x1008 || (o>=0x2000 && o+4<=0x3000));put32(mem+o,v);}
static void bell(void *c) {(void)c;rings++;}
static void nap(void *c,uint32_t n) {(void)c;clock_us+=n;}
static uint64_t now(void *c) {(void)c;return clock_us;}
static void rx(unsigned cmd,unsigned cid,uint32_t arg,const void *data,unsigned n) {
 uint32_t head=get32(mem+0x100c);uint8_t b[4096]={0};header(b,cmd,cid,arg);if(n)memcpy(b+8,data,n);
 unsigned len=(8+n+7)&~7u;assert(len<4096);
 for(unsigned i=0;i<len;i++)mem[0x4000+(head+i)%4096]=b[i];
 put32(mem+0x100c,(head+len)%4096);
}
static void drain(void) {put32(mem+0x1000,get32(mem+0x1004));}
static struct mi8_glink *fresh(void) {
 memset(mem,0,sizeof(mem));struct mi8_glink_cfg c={.name="test",.remote_pid=1,.smem_item=item,.smem_read=load,.smem_write32=store,.ring=bell,.sleep_us=nap,.now_us=now};
 struct mi8_glink *g=mi8_glink_create(&c);assert(g);return g;
}
static void qrtr(struct mi8_glink *g,unsigned type,unsigned service) {
 uint8_t b[8+52]={0};put32(b,52);put32(b+4,0);
 uint8_t *q=b+8;put32(q,1);put32(q+4,type);put32(q+8,0);put32(q+12,CTRL);put32(q+20,20);put32(q+24,1);put32(q+28,CTRL);
 put32(q+32,type);put32(q+36,service);put32(q+40,1|(180u<<8));put32(q+44,0);put32(q+48,23);
 rx(DATA,7,g->local[0].id,b,sizeof(b));mi8_glink_poll_once(g);drain();
}
int main(void) {
 struct mi8_glink *g=fresh();assert(mi8_glink_start(g)==0);assert(get32(mem+0x1004)==8 && rings);drain();
 rx(VERSION,1,1,NULL,0);rx(VERSION_ACK,1,1,NULL,0);rx(OPEN,7,7,"IPCRTR",7);mi8_glink_poll_once(g);drain();
 assert(g->agreed && g->remote==7 && g->asked && !g->broken);
 rx(OPEN_ACK,1,0,NULL,0);mi8_glink_poll_once(g);drain();assert(g->opened);
 uint8_t it[8];put32(it,4096);put32(it+4,0);rx(INTENT,7,1,it,8);mi8_glink_poll_once(g);drain();assert(g->foreign[0].there && g->foreign[0].id==0);
 qrtr(g,Q_HELLO,0);assert(g->hello && !g->broken);
 qrtr(g,Q_NEW_SERVER,66);struct mi8_qrtr_server s[4];assert(mi8_glink_qrtr_servers(g,s,4)==1 && s[0].service==66 && s[0].instance==180);
 qrtr(g,Q_DEL_SERVER,66);assert(mi8_glink_qrtr_servers(g,s,4)==0);
 mi8_glink_destroy(g);
 g=fresh();assert(mi8_glink_start(g)==0);put32(mem+0x100c,4096);mi8_glink_poll_once(g);assert(g->broken);mi8_glink_destroy(g);
 g=fresh();assert(mi8_glink_start(g)==0);rx(OPEN,7,0,NULL,0);mi8_glink_poll_once(g);assert(g->broken);mi8_glink_destroy(g);
 g=fresh();assert(mi8_glink_start(g)==0);rx(255,0,0,NULL,0);mi8_glink_poll_once(g);assert(g->broken);mi8_glink_destroy(g);
 g=fresh();assert(mi8_glink_start(g)==0);put32(mem+0x1008,4088);put32(mem+0x100c,4088);rx(VERSION,1,1,NULL,0);mi8_glink_poll_once(g);assert(!g->broken);mi8_glink_destroy(g);
 assert(allocs==0);return 0;
}
'''
 if probe_progress:
  harness=harness.replace('static struct mi8_glink *fresh(void)', 'static unsigned intent_logs,error_logs;\nstatic void testlog(void *c,const char *f,...) {(void)c;if(strstr(f,"remote intent id"))intent_logs++;if(strstr(f,"GLINK error"))error_logs++;}\nstatic struct mi8_glink *fresh(void)')
  harness=harness.replace('.now_us=now};', '.now_us=now,.log=testlog,.quiet_data=getenv("EQ_QUIET")!=NULL};')
  harness=harness.replace('qrtr(g,Q_HELLO,0);', 'assert(intent_logs==(getenv("EQ_QUIET")?0u:1u));qrtr(g,Q_HELLO,0);')
  harness=harness.replace('assert(allocs==0);return 0;', 'assert(allocs==0 && error_logs>0);return 0;')
 c=dev/'test.c';c.write_text(harness);exe=root/'test'
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-pthread',str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
 if probe_progress: subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0','EQ_QUIET':'1'})
 assert ('mss_glink_test = mode == 8 || mode == 9 || mode == 10 || mode == 12;' if rmtfs else 'mss_glink_test = mode == 8 || mode == 9 || mode == 10;' if hostsvc else 'mss_glink_test = mode == 8 || mode == 9;' if servreg else 'mss_glink_test = mode == 8;') in source
 assert source.index('equuleus_glink_probe();') < source.index('done:\n\t(void)dsp_ask_to_stop',source.index('equuleus_glink_probe();'))
 adapter=source[source.index('/* 0153:'):source.index('#define MAX_SEGMENTS 48u')]
 if not rmtfs: assert 'ml_io_' not in adapter and 'assign_mem' not in adapter and 'sweet_ufs' not in adapter
 else: assert 'if (mss_rmtfs_test && !eq_rmt_share_start(g))' in adapter
 print('0153 replay; actual GLINK VERSION/IPCRTR/intents/QRTR hello/service add/remove; malformed FIFO/commands/wrap and ASan/UBSan checks passed')
 prefix=r'''
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include "equuleus_glink.h"
#define SMEM_SIZE 65536u
#define SMEM_MODEM 1
#define IPC_GLINK_MODEM (1u<<12)
#define NSEC_PER_USEC 1000
#define DSP_FATAL 1u
struct smp2p {unsigned state;};
static uint8_t memory[SMEM_SIZE];static uint64_t elapsed;static unsigned writes,bells,scenario;
static void say(const char *f,...) {(void)f;}
static void settle(void) {}
static uint64_t now_us(void) {return elapsed;}
static void delay_for_interval(unsigned n,unsigned unit) {assert(unit==1000);elapsed+=n;}
static void ring(unsigned mask) {assert(mask==IPC_GLINK_MODEM);bells++;}
static bool smem_peek(uint64_t off,void *out,uint32_t n) {if(off+n>SMEM_SIZE || scenario==5)return false;memcpy(out,memory+off,n);return true;}
static void smem_poke(uint32_t off,uint32_t v) {assert(off==0x1004 || off==0x1008 || (off>=0x2000 && off+4<=0x3000));memcpy(memory+off,&v,4);writes++;}
static uint32_t adsp_item(uint32_t item,uint32_t *size) {
 if(scenario==1)return 0;
 *size=item==478?32:4096;
 if(scenario==2 && item==480)return 0x2000;
 if(scenario==3 && item==480)return SMEM_SIZE-8;
 return item==478?0x1000:item==479?0x2000:0x4000;
}
static bool dsp_words(struct smp2p *s) {s->state=scenario==4?1:2;return true;}
static uint32_t dsp_state(const struct smp2p *s) {return s->state;}
static void dsp_listen(const struct smp2p *s) {(void)s;}
'''
 main=r'''
int main(void) {
 for(scenario=0;scenario<6;scenario++) {
  memset(memory,0,sizeof(memory));elapsed=writes=bells=0;
  equuleus_glink_probe();assert(elapsed<=10000000ull);
  if(scenario==1 || scenario==2 || scenario==3)assert(writes==0 && bells==0);
 }
 scenario=0;struct eq_glink_io io;assert(eq_glink_layout(&io));
 unsigned before=writes;eq_glink_write(&io,0x4000,42);assert(io.fault && writes==before);
 unsigned old=bells;eq_glink_ring(&io);assert(bells==old);
 assert(eq_glink_layout(&io));uint8_t out[16];memset(out,1,sizeof(out));
 eq_glink_read(&io,SMEM_SIZE-1,out,16);assert(io.fault);for(unsigned i=0;i<16;i++)assert(out[i]==0);
 assert(!eq_glink_range(0xfffffff0,32,0xfffffff0,32));
 assert(!eq_glink_range(0x1fff,4,0x2000,4096));
 assert(!eq_glink_range(0x2fff,4,0x2000,4096));
 assert(eq_glink_range(0x2ffc,4,0x2000,4096));
 mss_glink_test=true;assert(mss_glink_test);
 return 0;
}
'''
 if servreg:
  prefix=prefix.replace('#include \"equuleus_glink.h\"', '#include \"equuleus_servreg.h\"')
  main=main.replace('equuleus_glink_probe();assert(elapsed<=10000000ull);', 'mss_servreg_test=true;equuleus_glink_probe();assert(elapsed<=20000000ull);')
 if hostsvc:
  prefix=prefix.replace('#include "equuleus_servreg.h"', '#include "equuleus_servreg.h"\n#include "mi8_hostsvc.h"')
  prefix+='''\nstruct fs_file {uint32_t size;bool dir;};
static bool fs_lookup(const char *p,struct fs_file *f) {(void)p;f->size=512;f->dir=false;return true;}
static int fs_file_read(const struct fs_file *f,uint64_t o,void *d,uint64_t n) {(void)f;(void)o;memset(d,0,n);return 0;}
'''
  main=main.replace('mss_servreg_test=true;equuleus_glink_probe();assert(elapsed<=20000000ull);', 'mss_servreg_test=true;mss_hostsvc_test=true;equuleus_glink_probe();assert(elapsed<=30000000ull);')
  main=main.replace('mss_glink_test=true;assert(mss_glink_test);', '''mss_glink_test=true;assert(mss_glink_test);
 assert(eq_firmware_path("image/wlanmdsp.mbn"));
 assert(!eq_firmware_path("image/../modemst1"));
 assert(!eq_firmware_path("modemst1"));
 assert(!eq_firmware_path("image/a/b"));
 uint64_t size;uint8_t data[8];
 assert(eq_firmware_size(NULL,"image/wlanmdsp.mbn",&size)==0 && size==512);
 assert(eq_firmware_read(NULL,"image/wlanmdsp.mbn",508,data,8)!=0);
 assert(eq_firmware_read(NULL,"image/wlanmdsp.mbn",504,data,8)==0);
 assert(eq_firmware_read(NULL,"image/wlanmdsp.mbn",UINT64_MAX,data,8)!=0);
''')
 if rmtfs:
  prefix+='''
#include "equuleus_rmtfs.h"
#include "equuleus_rmtfs_contract.h"
typedef uintptr_t vm_offset_t;
#define VMID_HLOS 3
static int sweet_ufs_part_size(const char *name,uint8_t *lun,uint64_t *size) {(void)name;*lun=5;*size=0x800000;return 0;}
static int sweet_ufs_read_part(const char *name,uint64_t at,void *out,uint64_t n) {(void)name;(void)at;memset(out,0,(size_t)n);return 0;}
static bool assign_mem(const char *name,uint32_t pa,uint32_t n,uint64_t *owners,bool local,bool remote) {(void)name;assert(pa==EQ_RMT_DATA && n==EQ_RMT_BYTES && *owners==8 && local && remote);*owners=0x8008;return true;}
'''
  main=main.replace('mss_glink_test=true;assert(mss_glink_test);', '''mss_glink_test=true;assert(mss_glink_test);
 uint64_t part_size;assert(!eq_rmt_part_size(NULL,"modemst1",&part_size));uint8_t b;assert(!eq_rmt_part_read(NULL,"modemst1",0,&b,1));
 mss_rmtfs_test=true;mss_rmtfs=NULL;elapsed=0;equuleus_glink_probe();assert(elapsed<=60000000ull && !mss_rmt_share_attempted);mss_rmtfs_test=false;
''')
 if probe_progress:
  main=main.replace('elapsed<=60000000ull','elapsed<=180000000ull')
  prefix=prefix.replace('static void delay_for_interval(unsigned n,unsigned unit)', 'static bool test_spin;\nstatic void delay_for_interval(unsigned n,unsigned unit)').replace('elapsed+=n;}', 'if(!test_spin)elapsed+=n;}')
  main=main.replace('mss_rmtfs_test=false;', 'mss_rmtfs_test=false;scenario=1;mss_rmtfs_test=true;test_spin=true;elapsed=0;equuleus_glink_probe();assert(strstr(exit_log,"reason=poll-cap"));test_spin=false;mss_rmtfs_test=false;')
  prefix=prefix.replace('static void say(const char *f,...) {(void)f;}', 'static char exit_log[256];static unsigned exit_count;\nstatic void say(const char *f,...) {if(strstr(f,"eqgl: exit reason=")){va_list a;va_start(a,f);vsnprintf(exit_log,sizeof(exit_log),f,a);va_end(a);exit_count++;}}')
  main=main.replace('if(scenario==1 || scenario==2 || scenario==3)assert(writes==0 && bells==0);', 'assert(exit_count && strstr(exit_log,"elapsed_us="));if(scenario==1 || scenario==2 || scenario==3){assert(writes==0 && bells==0);assert(strstr(exit_log,"reason=deadline"));}if(scenario==4)assert(strstr(exit_log,"reason=dsp-fault"));')
 if firmware_paths:
  prefix+='\n#define MIN(a,b) ((a)<(b)?(a):(b))\n'+source[source.index('static bool\nfs_component83('):source.index('/* Bounded nested FAT16 lookup;')]
 c=dev/'adapter.c';c.write_text(prefix+adapter+main)
 subprocess.run(['cc','-std=gnu11','-DMI8_GLINK_HOST_TEST','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-pthread',str(c),str(dev/'equuleus_glink.c'),*([str(dev/'equuleus_servreg.c')] if servreg else []),*([str(dev/'mi8_hostsvc.c')] if hostsvc else []),*(['-DEQ_RMTFS_HOST_TEST',str(dev/'equuleus_rmtfs.c')] if rmtfs else []),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
 print('Actual equuleus adapter: bounded probe, missing/overlapping/out-of-range items, fatal DSP, read failure and write allowlist checks passed')
 if rmtfs:
  print(('0164' if wlfw_register else '0163' if wlfw_cap else '0162' if probe_progress else '0161' if deep_mcfg else '0160' if firmware_paths else '0159' if tftp_replace else '0158' if tftp_ram else '0157')+' actual modified GLINK adapter compiled and checked: bounds, deadline and missing-prepared-RMTFS refusal')
  raise SystemExit(0)
 gate=source[source.index('void\nequuleus_mss_probe(void)'):].split('#endif',1)[0]
 prefix=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
static unsigned mode,calls,survey,rails;static bool board,mss_halt_all,mss_full_test,mss_glink_test;
static bool sweet_board_is(const char *s) {assert(!strcmp(s,"xiaomi,equuleus"));return board;}
static bool PE_parse_boot_argn(const char *s,void *v,size_t n) {assert(!strcmp(s,"sweetmss") && n==sizeof(mode));memcpy(v,&mode,n);return true;}
static void say(const char *s,...) {(void)s;}
static void mss_w2a(void) {survey++;}
static void mss_w2bc(unsigned n) {assert(n==2);rails++;}
static void mss_run_mba(void) {calls++;assert(mss_halt_all==(mode==7));assert(mss_full_test==(mode>=6));assert(mss_glink_test==(mode==8));}
'''
 main=r'''
int main(int argc,char **argv) {
 assert(argc==3);mode=(unsigned)atoi(argv[1]);board=atoi(argv[2]);
 equuleus_mss_probe();equuleus_mss_probe();
 assert(calls==(unsigned)(board && mode>=5 && mode<=8));
 assert(rails==(unsigned)(board && mode==2));
 assert(survey==(unsigned)(board && (mode==1 || mode==2 || (mode>=5 && mode<=8))));
 return 0;
}
'''
 if servreg:
  prefix=prefix.replace('mss_glink_test;', 'mss_glink_test,mss_servreg_test;').replace('mode==8));', 'mode==8 || mode==9));assert(mss_servreg_test==(mode==9));')
  main=main.replace('mode<=8', 'mode<=9')
 if hostsvc:
  prefix=prefix.replace('mss_servreg_test;', 'mss_servreg_test,mss_hostsvc_test;').replace('mode==8 || mode==9));', 'mode>=8 && mode<=10));').replace('mss_servreg_test==(mode==9)', 'mss_servreg_test==(mode==9 || mode==10)')
  prefix=prefix.replace('static void mss_run_mba(void) {', 'static void mss_run_mba(void) {assert(mss_hostsvc_test==(mode==10));')
  main=main.replace('mode<=9', 'mode<=10')
 c.write_text(prefix+gate+main)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
 for mode in [0,1,2,3,5,6,7,8,9]+([10] if servreg else [])+([11] if hostsvc else []):
  for board in [0,1]:subprocess.run([str(exe),str(mode),str(board)],check=True)
 print('%u actual boot-entry mode/board cases passed; one-shot and mode gates verified (0154=%s)' % (22 if hostsvc else 20 if servreg else 18,servreg))
