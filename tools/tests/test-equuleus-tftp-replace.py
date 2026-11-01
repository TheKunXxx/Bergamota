#!/usr/bin/env python3
"""Replay through 0159 and test actual bounded RAM replacement and diagnostics."""
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
 for pre in ['0150','0151','0152','0153','0154','0155','0156','0157','0158','0159']:
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
#include <stdarg.h>
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
 assert(p->live && node==0 && port>0 && n<=sizeof(output));memcpy(output,data,n);output_size=n;transmitted++;
 if(reentrant){uint8_t bad[2]={0,0};callbacks[0](contexts[0],0,17,bad,2);}
 return 0;
}
static void cl(struct redwood_qrtr_port *p){assert(p->live);p->live=false;closed++;}
static int pub(void *ctx,struct redwood_qrtr_port *p,uint32_t service,uint32_t version,uint32_t instance) {
 (void)ctx;assert(p->live && version==1 && ((service==4096 && instance==0)||(service==64 && instance==1)));
 if(++published==fail_publish)return 5;return 0;
}
static int size_file(void *ctx,const char *path,uint64_t *size){(void)ctx;if(strcmp(path,"image/wlanmdsp.mbn"))return 2;if(missing)return 2;*size=600;return 0;}
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
static void deliver_peer(struct mi8_hostsvc *h,unsigned ep,unsigned peer,const void *p,unsigned n) {
 callbacks[ep](contexts[ep],0,peer,p,n);mi8_hostsvc_poll(h);
}
static unsigned files_live(struct mi8_hostsvc *h){unsigned n=0;for(unsigned i=0;i<RAM_FILES;i++)n+=h->files[i].bytes!=NULL;return n;}
static unsigned request_name(uint8_t *out,unsigned opcode,const char *name){unsigned n=strlen(name);out[0]=0;out[1]=opcode;memcpy(out+2,name,n+1);memcpy(out+3+n,"octet",6);return n+9;}
static unsigned current_file(struct mi8_hostsvc *h,const char *name){for(unsigned i=0;i<RAM_FILES;i++)if(h->files[i].bytes && h->files[i].current && !strcmp(h->files[i].path,name))return i;assert(0);return 0;}
static char logbuf[32768];static unsigned loglen;
static void capture(void *c,const char *fmt,...){(void)c;va_list a;va_start(a,fmt);int n=vsnprintf(logbuf+loglen,sizeof(logbuf)-loglen,fmt,a);va_end(a);if(n>0 && (unsigned)n<sizeof(logbuf)-loglen)loglen+=n;}
int main(void) {
 uint8_t wrq[256],rrq[256],data[516]={0,3,0,1},ack[4]={0,4,0,1};
 unsigned wn=request_name(wrq,2,"readwrite/mcfg.tmp"),rn=request_name(rrq,1,"readwrite/mcfg.tmp");
 memset(data+4,'A',512);
 struct mi8_hostsvc *h=fresh();h->cfg.ram_writes=1;h->cfg.log=capture;assert(!mi8_hostsvc_start(h));
 deliver_peer(h,0,17,wrq,wn);assert(getbe16(output)==4);
 deliver_peer(h,0,17,data,516);data[3]=2;deliver_peer(h,0,17,data,92);
 unsigned oldslot=current_file(h,"image/readwrite/mcfg.tmp");assert(h->files[oldslot].size==600 && h->ram_commits==1);
 /* Reader18 has old version while writer19 stages replacement. */
 deliver_peer(h,0,18,rrq,rn);assert(output_size==516 && output[4]=='A');
 deliver_peer(h,0,19,wrq,wn);assert(getbe16(output)==4 && files_live(h)==2);
 unsigned staged=oldslot?0:1;assert(h->files[staged].bytes && !h->files[staged].current);
 /* Same WRQ retries ACK0; second writer refused, current data stays readable. */
 deliver_peer(h,0,19,wrq,wn);assert(getbe16(output)==4 && getbe16(output+2)==0 && files_live(h)==2);
 deliver_peer(h,0,21,wrq,wn);assert(getbe16(output)==5 && getbe16(output+2)==6);
 deliver_peer(h,0,20,rrq,rn);assert(output_size==516 && output[4]=='A');
 uint8_t err[5]={0,5,0,0,0};deliver_peer(h,0,20,err,5);
 /* CommitB, keep old reader pinned; a new reader sees B immediately. */
 data[3]=1;memset(data+4,'B',3);deliver_peer(h,0,19,data,7);assert(getbe16(output)==4 && h->ram_replacements==1 && files_live(h)==2);
 deliver_peer(h,0,19,data,7);assert(h->ram_commits==2);
 deliver_peer(h,0,20,rrq,rn);assert(output_size==7 && output[4]=='B');deliver_peer(h,0,20,ack,4);
 deliver_peer(h,0,18,ack,4);assert(output_size==92 && output[4]=='A');ack[3]=2;deliver_peer(h,0,18,ack,4);
 assert(!h->files[oldslot].bytes && files_live(h)==1 && h->ram_readbacks==2);
 /* Failed allocation does not alter committed B. */
 fail_alloc=attempt_alloc+2;deliver_peer(h,0,19,wrq,wn);fail_alloc=0;assert(getbe16(output)==5 && files_live(h)==1);
 deliver_peer(h,0,20,rrq,rn);assert(output_size==7 && output[4]=='B');ack[3]=1;deliver_peer(h,0,20,ack,4);
 /* Partial upload error/cancel leaves B current and releases staging RAM. */
 deliver_peer(h,0,19,wrq,wn);data[3]=1;memset(data+4,'C',512);deliver_peer(h,0,19,data,516);
 deliver_peer(h,0,19,err,5);assert(files_live(h)==1);
 deliver_peer(h,0,20,rrq,rn);assert(output_size==7 && output[4]=='B');deliver_peer(h,0,20,ack,4);
 /* Repeated real modem filename cycles reuse RAM, no eight-file exhaustion. */
 for(unsigned i=0;i<40;i++){deliver_peer(h,0,19,wrq,wn);assert(getbe16(output)==4);data[3]=1;data[4]=(uint8_t)i;deliver_peer(h,0,19,data,5);assert(getbe16(output)==4 && files_live(h)==1);}
 assert(h->ram_replacements==41);
 /* Abandoning a session with a different request also frees staging. */
 deliver_peer(h,0,19,wrq,wn);unsigned other=request_name(wrq,2,"readwrite/other.tmp");deliver_peer(h,0,19,wrq,other);assert(files_live(h)==2);
 deliver_peer(h,0,19,err,5);assert(files_live(h)==1);
 /* Missing filename and unconditional summary survive verbose logging. */
 unsigned missing=request_name(rrq,1,"readwrite/absent.cfg");deliver_peer(h,0,20,rrq,missing);
 assert(getbe16(output)==5 && strstr(logbuf,"tftp missing file=image/readwrite/absent.cfg") && h->missing_files==1);
 h->logs[LOG_OTHER]=21;mi8_hostsvc_stop(h);assert(strstr(logbuf,"mi8hs: summary requests=") && strstr(logbuf,"replacements=41"));mi8_hostsvc_destroy(h);assert(!allocations);
 /* Eight distinct committed files: replacement refuses without losing old. */
 h=fresh();h->cfg.ram_writes=1;assert(!mi8_hostsvc_start(h));
 for(unsigned i=0;i<8;i++){char name[8]="file0";name[4]='0'+i;wn=request_name(wrq,2,name);deliver(h,0,wrq,wn);data[3]=1;deliver(h,0,data,5);assert(getbe16(output)==4);}
 wn=request_name(wrq,2,"file0");deliver(h,0,wrq,wn);assert(getbe16(output)==5 && getbe16(output+2)==3 && files_live(h)==8);
 rn=request_name(rrq,1,"file0");deliver(h,0,rrq,rn);assert(getbe16(output)==3 && output_size==5);
 mi8_hostsvc_destroy(h);assert(!allocations);
 /* Parser mutations on actual replacement-enabled service. */
 h=fresh();h->cfg.ram_writes=1;assert(!mi8_hostsvc_start(h));uint32_t seed=29;
 for(unsigned i=0;i<2000;i++){uint8_t copy[256];memcpy(copy,wrq,wn);seed=seed*1664525u+1013904223u;copy[seed%wn]^=(uint8_t)(1+(seed>>16));deliver(h,0,copy,wn);}
 mi8_hostsvc_destroy(h);assert(!allocations);
 puts("0159 actual TFTP: atomic replacement, pinned old reader/new reader, duplicate WRQ/DATA, competing writer, failed allocation, aborted upload, 40 replacements, capacity refusal, missing filename/summary, zeroed frees and 2000 mutations passed");
 return 0;
}
'''
 c=dev/'test.c';c.write_text(harness);exe=root/'test'
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wno-unused-function','-fsanitize=address,undefined','-I',str(dev),str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
