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
 for pre in ['0150','0151','0152','0153','0154','0155','0156','0157','0158','0159','0160','0161','0162']:
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
static unsigned tx_error;static uint8_t output[4096];static unsigned output_size;static bool missing,read_error,reentrant;
static struct redwood_qrtr_port *op(redwood_qrtr_receive_t cb,redwood_qrtr_server_t server,void *ctx) {
 (void)server;if(opened==fail_open)return NULL;assert(opened<2);unsigned id=opened++;ports[id].id=id;ports[id].live=true;callbacks[id]=cb;contexts[id]=ctx;return &ports[id];
}
static int tx(struct redwood_qrtr_port *p,uint32_t node,uint32_t port,const void *data,size_t n) {
 assert(p->live && node==0 && port>0 && n<=sizeof(output));memcpy(output,data,n);output_size=n;transmitted++;
 if(reentrant){uint8_t bad[2]={0,0};callbacks[0](contexts[0],0,17,bad,2);}
 return tx_error;
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
 uint8_t rrq[128],wrq[128],data[8]={0,3,0,1,'x'},ack[4]={0,4,0,1};
 unsigned rn=request_name(rrq,1,"wlanmdsp.mbn"),wn=request_name(wrq,2,"readwrite/probe.tmp");
 struct mi8_hostsvc *h=fresh();h->cfg.ram_writes=1;h->cfg.log=capture;assert(!mi8_hostsvc_start(h));
 deliver_peer(h,0,17,rrq,rn);assert(h->data_sent==512 && h->rrq_complete==0);
 deliver_peer(h,0,18,wrq,wn);assert(getbe16(output)==4);
 uint8_t q[256];unsigned n=qmi(q,"wlan/fw",0);callbacks[1](contexts[1],0,19,q,n);
 unsigned txs=transmitted,queued=h->queued;loglen=0;logbuf[0]=0;mi8_hostsvc_snapshot(h);
 assert(h->queued==queued && transmitted==txs && strstr(logbuf,"active_rrq=1 active_wrq=1 queued=1") && strstr(logbuf,"file=image/wlanmdsp.mbn bytes=512 size=600") && strstr(logbuf,"oack=0"));
 mi8_hostsvc_poll(h);deliver_peer(h,0,17,ack,4);assert(h->data_sent==600);ack[3]=2;deliver_peer(h,0,17,ack,4);assert(h->rrq_complete==1);
 deliver_peer(h,0,18,data,5);assert(h->ram_commits==1);
 /* Completed transfers disappear from active list, counters remain exact. */
 loglen=0;logbuf[0]=0;mi8_hostsvc_snapshot(h);assert(strstr(logbuf,"active_rrq=0 active_wrq=0 queued=0") && strstr(logbuf,"rrq_done=1"));
 /* No-response request is distinct from a failed response attempt. */
 unsigned prev=h->no_reply;uint8_t err[5]={0,5,0,0,0};deliver_peer(h,0,20,err,5);assert(h->no_reply==prev+1);
 h->received[1]=TFTP_BUDGET;prev=h->budget_drops;callbacks[0](contexts[0],0,17,rrq,rn);assert(h->budget_drops==prev+1 && !h->queued);
 h->received[1]=0;for(unsigned i=0;i<8;i++)callbacks[0](contexts[0],0,17,rrq,rn);assert(h->queued==6 && h->queue_drops==2 && h->queue_peak==6);
 callbacks[1](contexts[1],0,19,q,n);assert(h->queued==7);
 loglen=0;logbuf[0]=0;mi8_hostsvc_stop(h);assert(strstr(logbuf,"queued=7") && strstr(logbuf,"queue_drops=2") && strstr(logbuf,"mi8hs: summary"));mi8_hostsvc_destroy(h);assert(!allocations);
 /* A transport error increments the error count and never counts sent bytes. */
 h=fresh();h->cfg.ram_writes=1;assert(!mi8_hostsvc_start(h));tx_error=5;deliver(h,0,rrq,rn);assert(h->send_errors==1 && !h->data_sent);tx_error=0;
 fail_alloc=attempt_alloc+1;callbacks[0](contexts[0],0,17,rrq,rn);fail_alloc=0;assert(h->alloc_drops==1 && !h->queued);
 /* Extended finite budget accepts past8192, rejects at32768; PD independent. */
 h->received[1]=8192;deliver(h,0,rrq,rn);assert(h->received[1]==8193);
 h->received[1]=TFTP_BUDGET;callbacks[0](contexts[0],0,17,rrq,rn);assert(h->budget_drops==1);
 h->answered[1]=TFTP_BUDGET;assert(send_reply(h,1,0,17,data,5)!=0 && h->reply_cap_drops==1);deliver(h,1,q,n);assert(h->received[2]==1);mi8_hostsvc_destroy(h);assert(!allocations);
 /* Default old mode retains128 request budget and verbose log policy. */
 h=fresh();assert(!mi8_hostsvc_start(h));h->requests=128;callbacks[0](contexts[0],0,17,rrq,rn);assert(h->budget_drops==1);
 h->cfg.log=capture;h->logs[LOG_OTHER]=4;assert(log_due(h,LOG_OTHER));h->cfg.ram_writes=1;h->logs[LOG_OTHER]=4;assert(!log_due(h,LOG_OTHER));
 mi8_hostsvc_destroy(h);assert(!allocations);
 puts("0162 actual host service: side-effect-free active snapshots, completion/bytes, pending queue, no-response/send errors, queue/allocation/budget reasons, finite32768 budget and old mode preservation passed");return 0;
}
'''
 c=dev/'test.c';c.write_text(harness);exe=root/'test'
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wno-unused-function','-fsanitize=address,undefined','-I',str(dev),str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
