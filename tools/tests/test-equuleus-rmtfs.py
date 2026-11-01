#!/usr/bin/env python3
"""Actual RMTFS snapshots, protocol handlers, kernel ownership gates and failure tests."""
from pathlib import Path
import subprocess,tempfile,os
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as td:
 root=Path(td);dev=root/'bsd/dev';dev.mkdir(parents=True)
 t=(repo/'xnu/patches/0149-equuleus-mss-mba-bringup.patch').read_text().split('+++ b/bsd/dev/equuleus_mss.c\n',1)[1]
 (dev/'equuleus_mss.c').write_text('\n'.join(l[1:] for l in t.splitlines() if l.startswith('+'))+'\n')
 conf=root/'bsd/conf/files';conf.parent.mkdir(parents=True);conf.write_text('prefix\n'*117+'bsd/dev/beryllium_wlan.c\t\tstandard\nbsd/dev/equuleus_mss.c\t\tstandard\nbsd/dev/beryllium_bt_hci.c\t\tstandard\n'+'suffix\n'*12)
 subprocess.run(['git','init','-q',td],check=True)
 for pre in ['0150','0151','0152','0153','0154','0155','0156','0157']:
  patch=next((repo/'xnu/patches').glob(pre+'-*'));subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True);subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
 harness=r'''
#define EQ_RMTFS_HOST_TEST
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
static unsigned allocations,alloc_calls,fail_alloc;
static void *alloc(size_t n){if(++alloc_calls==fail_alloc)return NULL;void *p=calloc(1,n);if(p)allocations++;return p;}
static void release(void *p,size_t n){if(!p)return;assert(allocations);if(n==0x800000 || n==0x40000 || n==0x100000)for(size_t i=0;i<n;i++)assert(((uint8_t *)p)[i]==0);allocations--;free(p);}
#define RMT_ALLOC(n) alloc(n)
#define RMT_FREE(p,n) release(p,n)
#include "equuleus_rmtfs.c"
static unsigned size_calls,read_calls,closed,send_calls,published,fail_size,fail_read;
static uint64_t read_bytes;static uint8_t *shared;static uint8_t response[32];static unsigned rn;
static bool open_fail,publish_fail,reentrant;static redwood_qrtr_receive_t receiver;static void *context;
struct redwood_qrtr_port {unsigned live;};static struct redwood_qrtr_port port;
static int part_size(void *c,const char *name,uint64_t *n){(void)c;assert(size_calls<4 && !strcmp(name,rmt_names[size_calls]));*n=rmt_sizes[size_calls++];return size_calls==fail_size?5:0;}
static int part_read(void *c,const char *name,uint64_t at,void *out,uint64_t n){(void)c;unsigned i=0;while(i<4 && strcmp(name,rmt_names[i]))i++;assert(i<4 && at+n<=rmt_sizes[i] && n<=0x10000);read_calls++;read_bytes+=n;memset(out,1+i,n);return read_calls==fail_read?5:0;}
static struct redwood_qrtr_port *op(redwood_qrtr_receive_t cb,redwood_qrtr_server_t server,void *ctx){(void)server;if(open_fail)return NULL;receiver=cb;context=ctx;port.live=1;return &port;}
static int tx(struct redwood_qrtr_port *p,uint32_t node,uint32_t remote,const void *data,size_t n){assert(p==&port && p->live && node==0 && remote && n<=32);memcpy(response,data,n);rn=(unsigned)n;send_calls++;if(reentrant)receiver(context,0,remote,data,n);return 0;}
static void cl(struct redwood_qrtr_port *p){assert(p==&port && p->live);p->live=0;closed++;}
static const struct redwood_qrtr_ops ops={op,tx,NULL,cl};
static int publish(void *c,struct redwood_qrtr_port *p,uint32_t s,uint32_t v,uint32_t i){(void)c;assert(p==&port && s==14 && v==1 && i==1);published++;return publish_fail?5:0;}
static struct equuleus_rmtfs *fresh(void){size_calls=read_calls=closed=send_calls=published=0;read_bytes=0;fail_size=fail_read=0;open_fail=publish_fail=reentrant=false;struct equuleus_rmtfs_cfg cfg={.shared=shared,.physical=0xa8008000,.size=0x200000,.part_size=part_size,.part_read=part_read};return equuleus_rmtfs_create(&cfg);}
static unsigned qmi(uint8_t *p,unsigned txn,unsigned msg){memset(p,0,RMT_MAX);rmt_put(p+1,txn,2);rmt_put(p+3,msg,2);return 7;}
static unsigned tlv(uint8_t *p,unsigned n,unsigned tag,const void *v,unsigned z){p[n]=tag;rmt_put(p+n+1,z,2);memcpy(p+n+3,v,z);return n+3+z;}
static unsigned num(uint8_t *p,unsigned n,unsigned tag,uint64_t v,unsigned z){uint8_t a[8];rmt_put(a,v,z);return tlv(p,n,tag,a,z);}
static void finish(uint8_t *p,unsigned n){rmt_put(p+5,n-7,2);}
static void request(struct equuleus_rmtfs *r,uint8_t *p,unsigned n,uint32_t remote){finish(p,n);unsigned old=send_calls;receiver(context,0,remote,p,n);assert(send_calls==old);equuleus_rmtfs_poll(r);assert(send_calls==old+1 && response[0]==2 && rmt_le(response+1,2)==rmt_le(p+1,2) && rmt_le(response+3,2)==rmt_le(p+3,2));}
static unsigned error(void){return (unsigned)rmt_le(response+12,2);}
static uint32_t open_path(struct equuleus_rmtfs *r,unsigned txn,unsigned index,uint32_t remote){uint8_t p[RMT_MAX];unsigned n=qmi(p,txn,1);n=tlv(p,n,1,rmt_paths[index],strlen(rmt_paths[index]));request(r,p,n,remote);assert(!error() && rn==21);return (uint32_t)rmt_le(response+17,4);}
static unsigned rw(uint8_t *p,unsigned txn,uint32_t id,unsigned direction,unsigned count,uint32_t sector,uint32_t physical,uint32_t sectors){unsigned n=qmi(p,txn,3);n=num(p,n,1,id,4);n=num(p,n,2,direction,1);uint8_t vec[1+12*2]={0};assert(count<=2);vec[0]=(uint8_t)count;for(unsigned i=0;i<count;i++){rmt_put(vec+1+12*i,sector,4);rmt_put(vec+5+12*i,physical,4);rmt_put(vec+9+12*i,sectors,4);}return tlv(p,n,3,vec,1+12*count);}
int main(void){
 shared=calloc(1,0x200000);assert(shared);struct equuleus_rmtfs *r=fresh();assert(r && size_calls==4 && read_calls==388 && read_bytes==25427968);
 assert(equuleus_rmtfs_start(r,&ops,publish,NULL)==0 && published==1);
 uint8_t p[RMT_MAX],saved[RMT_MAX];unsigned n=qmi(p,1,4);n=num(p,n,1,1,4);n=num(p,n,2,0x200000,4);request(r,p,n,17);assert(!error() && rn==25 && rmt_le(response+17,8)==0xa8008000);
 n=qmi(p,2,4);n=num(p,n,1,2,4);n=num(p,n,2,0x1000,4);request(r,p,n,17);assert(error()==R_INVALID);
 uint32_t id=open_path(r,3,0,17);uint32_t fsg=open_path(r,4,2,19);
 n=rw(p,5,fsg,1,1,0,0xa8008000,1);request(r,p,n,33);assert(!error() && shared[0]==3 && shared[511]==3);
 memset(shared,0xa7,512);n=rw(p,6,id,0,1,0,0xa8008000,1);request(r,p,n,34);assert(!error() && r->shadow[0][0]==0xa7);memcpy(saved,p,n);
 memset(shared,0xb8,512);request(r,saved,n,34);assert(!error() && r->shadow[0][0]==0xa7 && r->replayed==1 && r->writes==1);
 /* Invalid final vector cannot partially modify the first vector's destination. */
 n=rw(p,7,id,0,2,1,0xa8008000,1);rmt_put(p+n-12,0xffffffffu,4);request(r,p,n,35);assert(error()==R_INVALID && r->shadow[0][512]==1);
 n=rw(p,8,id,1,2,0,0xa8008000,1);rmt_put(p+n-8,0xffffffffu,4);memset(shared,0x66,512);request(r,p,n,35);assert(error()==R_INVALID && shared[0]==0x66);
 n=rw(p,9,id,1,1,0,0xa8007fff,1);request(r,p,n,17);assert(error()==R_INVALID);
 n=rw(p,10,id,1,1,0,0xa8207fff,1);request(r,p,n,17);assert(error()==R_INVALID);
 n=rw(p,11,id,2,1,0,0xa8008000,1);request(r,p,n,17);assert(error()==R_INVALID);
 n=rw(p,12,id,1,0,0,0xa8008000,1);request(r,p,n,17);assert(error()==R_INVALID);
 n=rw(p,13,id,1,1,0,0xa8008000,0xffffffffu);request(r,p,n,17);assert(error()==R_INVALID);
 n=rw(p,14,id,1,2,0,0xa8008000,0x1000);request(r,p,n,17);assert(error()==R_INVALID); /* aggregate exceeds buffer */
 uint32_t oem=open_path(r,15,4,17);n=rw(p,16,oem,1,1,0,0xa8008000,1);request(r,p,n,17);assert(!error() && shared[0]==0 && read_calls==388);
 n=qmi(p,17,6);n=num(p,n,1,id,4);request(r,p,n,17);assert(!error());
 n=qmi(p,18,5);n=num(p,n,1,id,4);request(r,p,n,17);assert(!error() && rmt_le(response+17,4)==0);
 n=qmi(p,19,2);n=num(p,n,1,id,4);request(r,p,n,17);assert(!error());
 n=rw(p,20,id,1,1,0,0xa8008000,1);request(r,p,n,17);assert(error()==R_BAD_HANDLE);
 n=qmi(p,21,1);n=tlv(p,n,1,"/boot/unknown",13);request(r,p,n,17);assert(error()==R_INVALID);
 n=qmi(p,22,4);n=num(p,n,1,1,4);n=num(p,n,1,1,4);request(r,p,n,17);assert(error()==R_MALFORMED);
 n=qmi(p,23,99);request(r,p,n,17);assert(error()==R_UNSUPPORTED);
 /* Queue cap, peer allowlist, no recursive dispatch when send pumps input. */
 unsigned before=r->rejected;receiver(context,7,17,p,n);assert(r->rejected==before+1);
 for(unsigned i=0;i<12;i++)receiver(context,0,17,p,n);assert(r->queued==8);
 unsigned old=send_calls;reentrant=true;equuleus_rmtfs_poll(r);reentrant=false;assert(send_calls==old+1 && r->queued<=8);
 equuleus_rmtfs_destroy(r);assert(closed==1 && allocations==0);
 /* Bounded handles and request/reply budgets. */
 r=fresh();assert(r && !equuleus_rmtfs_start(r,&ops,publish,NULL));
 for(unsigned i=0;i<32;i++)open_path(r,i+1,0,17);
 n=qmi(p,33,1);n=tlv(p,n,1,rmt_paths[0],strlen(rmt_paths[0]));request(r,p,n,17);assert(error()==R_NOMEM);
 for(unsigned i=34;i<=4096;i++){n=qmi(p,i,99);request(r,p,n,17);}assert(r->requests==4096 && r->replies==4096);
 finish(p,n);receiver(context,0,17,p,n);assert(!r->queued);equuleus_rmtfs_destroy(r);assert(!allocations);
 /* All snapshot reads/allocations are cleaned on early/middle/last failures. */
 for(unsigned which=1;which<=4;which++){struct equuleus_rmtfs_cfg cfg={.shared=shared,.physical=0xa8008000,.size=0x200000,.part_size=part_size,.part_read=part_read};size_calls=read_calls=0;fail_size=which;fail_read=0;assert(!equuleus_rmtfs_create(&cfg) && !allocations);}
 fail_size=0;
 for(unsigned which=1;which<=388;which+=(which==1?193:194)){struct equuleus_rmtfs_cfg cfg={.shared=shared,.physical=0xa8008000,.size=0x200000,.part_size=part_size,.part_read=part_read};size_calls=read_calls=0;fail_read=which;assert(!equuleus_rmtfs_create(&cfg) && !allocations);}
 fail_read=0;
 for(unsigned i=1;i<=7;i++){fail_alloc=alloc_calls+i;r=fresh();assert(!r && !allocations);fail_alloc=0;}
 r=fresh();open_fail=true;assert(equuleus_rmtfs_start(r,&ops,publish,NULL)!=0);equuleus_rmtfs_destroy(r);assert(!allocations);
 r=fresh();publish_fail=true;assert(equuleus_rmtfs_start(r,&ops,publish,NULL)!=0 && closed==1);equuleus_rmtfs_destroy(r);assert(!allocations);
 /* Parser allocation failure, malformed length and mutation smoke tests. */
 r=fresh();assert(r && !equuleus_rmtfs_start(r,&ops,publish,NULL));n=qmi(p,1,4);n=num(p,n,1,1,4);n=num(p,n,2,4096,4);finish(p,n);receiver(context,0,17,p,n);fail_alloc=alloc_calls+1;equuleus_rmtfs_poll(r);fail_alloc=0;assert(error()==R_NOMEM);request(r,p,n,17);assert(!error());
 uint32_t seed=11;
 for(unsigned i=0;i<2000;i++){n=qmi(p,i+2,4);n=num(p,n,1,1,4);n=num(p,n,2,4096,4);finish(p,n);seed=seed*1664525u+1013904223u;p[seed%n]^=(uint8_t)(1+(seed>>16));receiver(context,0,17,p,n);equuleus_rmtfs_poll(r);}
 equuleus_rmtfs_destroy(r);assert(!allocations);free(shared);
 puts("Actual 0157 RMTFS: full snapshots, READ/WRITE-to-RAM, ALLOC/client-id, cross-port handles, replay, atomic bounds, OEM RAM, queue/budget, failure cleanup and 2000 mutations passed");return 0;}
'''
 c=dev/'test.c';c.write_text(harness);exe=root/'test';env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'}
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-I',str(dev),str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,env=env)
 # Compile the actual kernel preparation, SCM gate and board entry together.
 source=(dev/'equuleus_mss.c').read_text()
 callbacks=source[source.index('extern int sweet_ufs_part_size',source.index('static const struct mi8_pd_domain')):source.index('void\nequuleus_glink_probe(void)')]
 guards=source[source.index('static bool eq_rmt_guards'):source.index('void equuleus_rmtfs_preflight(void)')]
 prepare=source[source.index('/* Full snapshot and CPU contract checks'):source.index('void\nequuleus_mss_probe(void)')]
 gate=source[source.index('void\nequuleus_mss_probe(void)'):].split('#endif',1)[0]
 prefix=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include "equuleus_rmtfs.h"
#include "equuleus_rmtfs_contract.h"
typedef uintptr_t vm_offset_t;
#define VMID_HLOS 3
#define PAGE_SIZE 16384u
#define VM_WIMG_WCOMB 1
#define VM_PROT_READ 1
#define VM_PROT_WRITE 2
static bool mss_halt_all,mss_full_test,mss_glink_test,mss_servreg_test,mss_hostsvc_test,mss_rmtfs_test;
static struct equuleus_rmtfs *mss_rmtfs;
static vm_offset_t mss_rmt_pool;
static bool mss_rmt_share_attempted,mss_rmt_shared;
static uint64_t mss_rmt_owners=8;
static unsigned scenario,mode=12,maps,creates,starts,destroys,scms,surveys,mbas,preflights;static bool board=true;
static uint8_t *memory;static int object;
static struct equuleus_rmtfs *client(void){return (struct equuleus_rmtfs *)&object;}
static void say(const char *s,...){(void)s;}
static void eq_glink_log(void *c,const char *s,...){(void)c;(void)s;}
static bool PE_parse_boot_argn(const char *s,void *v,size_t n){assert(n==4);if(!strcmp(s,"sweetmss")){memcpy(v,&mode,4);return true;}assert(!strcmp(s,"eqrmtfs_pool"));*(unsigned *)v=156;return scenario!=1;}
static vm_offset_t io_map(uint64_t p,uint64_t n,unsigned attr,unsigned prot,bool unmap){assert(p==EQ_RMT_POOL && n==EQ_RMT_SPAN && attr==1 && prot==3 && unmap);maps++;return scenario==2?0:(uintptr_t)memory;}
static int sweet_ufs_part_size(const char *n,uint8_t *lun,uint64_t *size){assert(!strcmp(n,"modemst1"));*lun=5;*size=0x800000;return 0;}
static int sweet_ufs_read_part(const char *n,uint64_t at,void *dst,uint64_t len){assert(!strcmp(n,"modemst1") && at==0 && len==1);*(uint8_t *)dst=7;return 0;}
static int eq_host_publish(void *c,struct redwood_qrtr_port *p,uint32_t s,uint32_t v,uint32_t i){(void)c;(void)p;(void)s;(void)v;(void)i;return 0;}
static const struct redwood_qrtr_ops ops={0};
const struct redwood_qrtr_ops *mi8_glink_qrtr_ops(struct mi8_glink *g){assert(g==(struct mi8_glink *)&object);return &ops;}
static bool assign_mem(const char *n,uint32_t p,uint32_t bytes,uint64_t *owner,bool local,bool remote){assert(!strcmp(n,"rmtfs") && p==EQ_RMT_DATA && bytes==EQ_RMT_BYTES && *owner==8 && local && remote);scms++;if(scenario==7)return false;*owner=0x8008;return true;}
struct equuleus_rmtfs *equuleus_rmtfs_create(const struct equuleus_rmtfs_cfg *c){assert(c->shared==memory+2*EQ_RMT_PAGE && c->physical==EQ_RMT_DATA && c->size==EQ_RMT_BYTES && !mss_rmt_share_attempted);uint64_t size;uint8_t data;assert(!c->part_size(c->ctx,"modemst1",&size) && size==0x800000);assert(!c->part_read(c->ctx,"modemst1",0,&data,1) && data==7);creates++;return scenario==6?NULL:client();}
int equuleus_rmtfs_start(struct equuleus_rmtfs *r,const struct redwood_qrtr_ops *o,int (*p)(void *,struct redwood_qrtr_port *,uint32_t,uint32_t,uint32_t),void *c){assert(r==client() && o==&ops && p==eq_host_publish && c==(void *)&object && mss_rmt_share_attempted && mss_rmt_shared && scms==1);starts++;return scenario==8?5:0;}
void equuleus_rmtfs_destroy(struct equuleus_rmtfs *r){assert(r==client());destroys++;}
static bool sweet_board_is(const char *s){assert(!strcmp(s,"xiaomi,equuleus"));return board;}
static void equuleus_rmtfs_preflight(void){preflights++;}
static void mss_w2a(void){surveys++;}static void mss_w2bc(unsigned n){(void)n;abort();}
static void mss_run_mba(void);
'''
 main=r'''
static void mss_run_mba(void){mbas++;assert(mode==12 && !mss_halt_all && mss_full_test && mss_glink_test && mss_servreg_test && mss_hostsvc_test && mss_rmtfs_test);bool result=eq_rmt_share_start((struct mi8_glink *)&object);assert(result==(scenario!=7 && scenario!=8));assert(!eq_rmt_share_start((struct mi8_glink *)&object) && scms==1);}
int main(int argc,char **argv){assert(argc==2);scenario=(unsigned)atoi(argv[1]);memory=calloc(1,EQ_RMT_SPAN);assert(memory);struct eq_rmt_contract c={EQ_RMT_MAGIC,1,EQ_RMT_POOL,EQ_RMT_SPAN,EQ_RMT_DATA,EQ_RMT_BYTES,EQ_RMT_GUARD,0};c.checksum=eq_rmt_checksum(&c);memcpy(memory,&c,sizeof(c));uint64_t *pool=(uint64_t *)memory;for(unsigned i=0;i<EQ_RMT_PAGE/8;i++)pool[EQ_RMT_PAGE/8+i]=pool[(2*EQ_RMT_PAGE+EQ_RMT_BYTES)/8+i]=EQ_RMT_GUARD;
 if(scenario==3)pool[0]^=1;if(scenario==4)pool[EQ_RMT_PAGE/8]=0;if(scenario==5)pool[2*EQ_RMT_PAGE/8]=1;
 if(scenario==9)board=false;if(scenario==10)mode=11;if(scenario==11)mode=13;
 equuleus_mss_probe();equuleus_mss_probe();
 bool run=scenario==0 || scenario==7 || scenario==8;assert(surveys==(unsigned)run && mbas==(unsigned)run && scms==(unsigned)run);assert(starts==(unsigned)(scenario==0 || scenario==8));assert(destroys==(unsigned)run && mss_rmtfs==NULL);assert(preflights==(unsigned)(scenario==10));
 if(scenario==1 || scenario>=9)assert(!maps && !creates);if(scenario==6)assert(creates==1 && !scms);
 if(run){assert(mss_rmt_share_attempted && mss_rmt_shared==(scenario!=7));assert(mss_rmt_owners==(scenario==7?8u:0x8008u));}
 free(memory);return 0;}
'''
 c.write_text(prefix+callbacks+guards+prepare+gate+main)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-I',str(dev),str(c),'-o',str(exe)],check=True)
 for scenario in range(12):subprocess.run([str(exe),str(scenario)],check=True,env=env)
 print('Actual 0157 kernel snapshot preparation, SCM-before-publish, uncertain-share/no-retry, publish failure, mode11 preservation and board/one-shot gates passed')
subprocess.run(['python3',str(repo/'tools/tests/test-equuleus-glink.py')],check=True,env={**os.environ,'EQUULEUS_TEST_0157':'1'})
