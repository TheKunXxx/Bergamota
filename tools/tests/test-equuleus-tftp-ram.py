#!/usr/bin/env python3
"""Replay 0155 and test the actual firmware-only donor service implementation."""
from pathlib import Path
import os,subprocess,tempfile
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as td:
 root=Path(td);dev=root/'bsd/dev';dev.mkdir(parents=True)
 tail=(repo/'xnu/patches/0149-equuleus-mss-mba-bringup.patch').read_text().split('+++ b/bsd/dev/equuleus_mss.c\n',1)[1]
 (dev/'equuleus_mss.c').write_text('\n'.join(l[1:] for l in tail.splitlines() if l.startswith('+'))+'\n')
 conf=root/'bsd/conf/files';conf.parent.mkdir(parents=True)
 conf.write_text(''.join('prefix%u\n'%i for i in range(117))+'bsd/dev/beryllium_wlan.c\t\tstandard\nbsd/dev/equuleus_mss.c\t\tstandard\nbsd/dev/beryllium_bt_hci.c\t\tstandard\n'+'suffix\n'*12)
 subprocess.run(['git','init','-q',td],check=True)
 for pre in ['0150','0151','0152','0153','0154','0155','0156','0157','0158']:
  patch=next((repo/'xnu/patches').glob(pre+'-*'))
  subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
  subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
 source=(dev/'mi8_hostsvc.c').read_text();assert 'rmtfs(' not in source
 header=(dev/'mi8_hostsvc.h').read_text();assert 'part_read' not in header and 'rmtfs_phys' not in header
 harness=r'''
#define MI8_GLINK_HOST_TEST
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned allocations,attempt_alloc,fail_alloc;
static void *allocate(size_t n) {if(++attempt_alloc==fail_alloc)return NULL;void *p=calloc(1,n);if(p)allocations++;return p;}
static void deallocate(void *p,size_t n) {if(p && n==2u*1024u*1024u)for(size_t i=0;i<n;i++)assert(((unsigned char *)p)[i]==0);if(p){assert(allocations);allocations--;free(p);}}
#define MI8_ALLOC(n) allocate(n)
#define MI8_FREE(p,n) deallocate(p,n)
#include "mi8_hostsvc.c"
struct redwood_qrtr_port {unsigned id;bool live;};
static struct redwood_qrtr_port ports[2];static redwood_qrtr_receive_t callbacks[2];static void *contexts[2];
static unsigned opened,published,closed,transmitted,reads;static unsigned fail_open,fail_publish;
static uint8_t output[4096];static unsigned output_size;static bool missing,read_error,reentrant;
static struct redwood_qrtr_port *op(redwood_qrtr_receive_t cb,redwood_qrtr_server_t server,void *ctx) {
 (void)server;if(opened==fail_open)return NULL;assert(opened<2);unsigned id=opened++;ports[id].id=id;ports[id].live=true;callbacks[id]=cb;contexts[id]=ctx;return &ports[id];
}
static int tx(struct redwood_qrtr_port *p,uint32_t node,uint32_t port,const void *data,size_t n) {
 assert(p->live && node==0 && port==17 && n<=sizeof(output));memcpy(output,data,n);output_size=n;transmitted++;
 if(reentrant){uint8_t bad[2]={0,0};callbacks[0](contexts[0],0,17,bad,2);}
 return 0;
}
static void cl(struct redwood_qrtr_port *p){assert(p->live);p->live=false;closed++;}
static int pub(void *ctx,struct redwood_qrtr_port *p,uint32_t service,uint32_t version,uint32_t instance) {
 (void)ctx;assert(p->live && version==1 && ((service==4096 && instance==0)||(service==64 && instance==1)));
 if(++published==fail_publish)return 5;return 0;
}
static int size_file(void *ctx,const char *path,uint64_t *size){(void)ctx;assert(!strcmp(path,"image/wlanmdsp.mbn"));if(missing)return 2;*size=600;return 0;}
static int read_file(void *ctx,const char *path,uint64_t offset,void *dst,uint64_t n){(void)ctx;assert(!strcmp(path,"image/wlanmdsp.mbn") && offset<=600 && n<=600-offset);reads++;if(read_error)return 5;memset(dst,0x5a,n);return 0;}
static const struct redwood_qrtr_ops ops={op,tx,NULL,cl};
static const char *const services[]={"wlan/fw"};
static const struct mi8_pd_domain domains[]={{"msm/modem/wlan_pd",180,services,1}};
static struct mi8_hostsvc *fresh(void) {
 opened=published=closed=0;fail_open=99;fail_publish=99;missing=read_error=reentrant=false;
 struct mi8_hostsvc_cfg cfg={.qrtr=&ops,.publish=pub,.file_size=size_file,.file_read=read_file,.domains=domains,.n_domains=1};
 struct mi8_hostsvc *h=mi8_hostsvc_create(&cfg);assert(h);return h;
}
static void log_noop(void *c,const char *f,...){(void)c;(void)f;}
static void deliver(struct mi8_hostsvc *h,unsigned ep,const void *p,unsigned n){unsigned old=transmitted;callbacks[ep](contexts[ep],0,17,p,n);assert(transmitted==old);mi8_hostsvc_poll(h);}
static unsigned qmi(uint8_t *p,const char *service,uint32_t offset) {
 struct builder b={p,7,256,false};memset(p,0,256);setle(p+1,0x1234,2);setle(p+3,0x21,2);
 add_tlv(&b,1,service,strlen(service));add_number(&b,0x10,offset,4);setle(p+5,b.n-7,2);return b.n;
}
int main(void) {
 uint8_t req[]={0,2,'d','u','m','p',0,'o','c','t','e','t',0};
 uint8_t data[516]={0,3,0,1};memset(data+4,0x31,512);
 struct mi8_hostsvc *h=fresh();h->cfg.ram_writes=1;assert(!mi8_hostsvc_start(h));
 deliver(h,0,req,sizeof(req));assert(getbe16(output)==4 && getbe16(output+2)==0);
 assert(h->sessions[0].ram_slot==1 && !h->files[0].complete);
 /* Unexpected future block ACKs zero without writing. */
 data[3]=2;deliver(h,0,data,sizeof(data));assert(!h->files[0].size && getbe16(output+2)==0);
 data[3]=1;deliver(h,0,data,sizeof(data));assert(h->files[0].size==512 && getbe16(output+2)==1);
 deliver(h,0,data,sizeof(data));assert(h->files[0].size==512 && getbe16(output)==4);
 data[4]^=1;deliver(h,0,data,sizeof(data));assert(getbe16(output)==5 && h->files[0].size==512);data[4]^=1;
 data[3]=2;deliver(h,0,data,11);assert(h->files[0].complete && h->files[0].size==519);
 deliver(h,0,data,11);assert(getbe16(output)==4 && h->files[0].size==519);
 /* RRQ reads retained bytes, never invokes firmware reader. */
 req[1]=1;unsigned old=reads;deliver(h,0,req,sizeof(req));assert(getbe16(output)==3 && output_size==516 && output[4]==0x31 && reads==old);
 uint8_t ack[]={0,4,0,1};deliver(h,0,ack,4);assert(output_size==11 && !memcmp(output+4,data+4,7));
 req[1]=2;deliver(h,0,req,sizeof(req));assert(getbe16(output)==5 && getbe16(output+2)==6);
 mi8_hostsvc_destroy(h);assert(allocations==0);
 /* WRQ OACK: first DATA is block one, not an ACK of OACK. */
 const uint8_t opt[]={0,2,'o','p','t',0,'o','c','t','e','t',0,'b','l','k','s','i','z','e',0,'8',0,'t','s','i','z','e',0,'9',0,'w','s','i','z','e',0,'8',0};
 h=fresh();h->cfg.ram_writes=1;assert(!mi8_hostsvc_start(h));
 deliver(h,0,opt,sizeof(opt));assert(getbe16(output)==6 && h->sessions[0].blocksize==8 && h->sessions[0].window==1);
 deliver(h,0,opt,sizeof(opt));assert(getbe16(output)==6);
 data[3]=1;deliver(h,0,data,12);assert(h->files[0].size==8 && getbe16(output)==4);
 data[3]=2;deliver(h,0,data,4);assert(getbe16(output)==5 && h->files[0].size==8 && !h->files[0].complete);
 deliver(h,0,data,5);assert(h->files[0].complete && h->files[0].size==9);
 mi8_hostsvc_destroy(h);assert(!allocations);
 /* Block-number wrap uses 64-bit progress, not 16-bit offsets. */
 h=fresh();h->cfg.ram_writes=1;assert(!mi8_hostsvc_start(h));deliver(h,0,opt,sizeof(opt));
 h->sessions[0].declared=false;h->sessions[0].acked=65535;h->files[0].size=65535ull*8;
 data[3]=0;deliver(h,0,data,12);assert(h->sessions[0].acked==65536 && h->files[0].size==65536ull*8);
 deliver(h,0,data,12);assert(h->files[0].size==65536ull*8);
 mi8_hostsvc_destroy(h);assert(!allocations);
 /* Empty files, actual byte limit and independent queue/budget reservations. */
 h=fresh();h->cfg.ram_writes=1;assert(!mi8_hostsvc_start(h));req[1]=2;
 deliver(h,0,req,sizeof(req));data[3]=1;deliver(h,0,data,4);assert(h->files[0].complete && !h->files[0].size);
 req[2]='x';deliver(h,0,req,sizeof(req));struct tftp *t=&h->sessions[0];struct ram_file *f=&h->files[t->ram_slot-1];
 f->size=RAM_FILE_BYTES;deliver(h,0,data,5);assert(getbe16(output)==5 && f->size==RAM_FILE_BYTES && !f->complete);
 h->received[1]=8192;unsigned before=h->requests;deliver(h,0,req,sizeof(req));assert(h->requests==before);
 uint8_t q[256];unsigned n=qmi(q,"wlan/fw",0);deliver(h,1,q,n);assert(h->requests==before+1 && output[0]==2);
 h->received[1]=0;for(unsigned i=0;i<10;i++)callbacks[0](contexts[0],0,17,req,sizeof(req));assert(h->queued==6);
 callbacks[1](contexts[1],0,17,q,n);assert(h->queued==7);
 mi8_hostsvc_destroy(h);assert(!allocations);
 /* Buffer allocation failure never yields ACK success. Eight files bound RAM. */
 h=fresh();h->cfg.ram_writes=1;assert(!mi8_hostsvc_start(h));fail_alloc=attempt_alloc+2;
 deliver(h,0,req,sizeof(req));assert(getbe16(output)==5 && !h->files[0].bytes);fail_alloc=0;
 for(unsigned i=0;i<8;i++){req[2]='a'+i;deliver(h,0,req,sizeof(req));assert(getbe16(output)==4);data[3]=1;deliver(h,0,data,4);}
 req[2]='z';deliver(h,0,req,sizeof(req));assert(getbe16(output)==5 && getbe16(output+2)==3);
 mi8_hostsvc_destroy(h);assert(!allocations);
 /* Mutate real WRQ parser, including path/options; all buffers reclaimed. */
 h=fresh();h->cfg.ram_writes=1;assert(!mi8_hostsvc_start(h));uint32_t seed=17;
 for(unsigned i=0;i<2000;i++){uint8_t copy[sizeof(opt)];memcpy(copy,opt,sizeof(opt));seed=seed*1664525u+1013904223u;copy[seed%sizeof(copy)]^=(uint8_t)(1+(seed>>16));deliver(h,0,copy,sizeof(copy));}
 mi8_hostsvc_destroy(h);assert(!allocations);
 puts("0158 actual TFTP RAM: WRQ/RRQ, options, retries, conflicts, tsize, bounds, budget isolation, queue reservation, allocation failure, eight-file cap, cleanup and 2000 mutations passed");
 return 0;
}
'''
 c=dev/'test.c';c.write_text(harness);exe=root/'test'
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wno-unused-function','-fsanitize=address,undefined','-I',str(dev),str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
