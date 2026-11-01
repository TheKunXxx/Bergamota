#!/usr/bin/env python3
"""Exercise actual 0164 C with fake QRTR, without touching hardware."""
from pathlib import Path
import os, subprocess, tempfile
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    p163=next((repo/'xnu/patches').glob('0163-*.patch')).read_text()
    tail=p163.split('+++ b/bsd/dev/equuleus_wlfw_probe.h\n',1)[1]
    dev=root/'bsd/dev';dev.mkdir(parents=True)
    (dev/'equuleus_wlfw_probe.h').write_text('\n'.join(l[1:] for l in tail.splitlines() if l.startswith('+'))+'\n')
    subprocess.run(['git','init','-q',str(root)],check=True)
    subprocess.run(['git','apply',str(next((repo/'xnu/patches').glob('0164-*.patch')))],cwd=root,check=True)
    # Only QRTR's ABI is stubbed. All parser, retry and state code is production C.
    (dev/'equuleus_glink.h').write_text('''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
struct redwood_qrtr_port;
typedef void (*redwood_qrtr_receive_t)(void *,uint32_t,uint32_t,const void *,size_t);
typedef void (*redwood_qrtr_server_t)(void *,bool,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
struct redwood_qrtr_ops {
 struct redwood_qrtr_port *(*open)(redwood_qrtr_receive_t,redwood_qrtr_server_t,void *);
 int (*send)(struct redwood_qrtr_port *,uint32_t,uint32_t,const void *,size_t);
 int (*lookup)(struct redwood_qrtr_port *,uint32_t,uint32_t,uint32_t);
 void (*close)(struct redwood_qrtr_port *);
};
''')
    (dev/'test.c').write_text(r'''
#include <assert.h>
#include <stdio.h>
#include "equuleus_wlfw_probe.h"
struct redwood_qrtr_port {int live;};static struct redwood_qrtr_port port;
static redwood_qrtr_receive_t receive;static redwood_qrtr_server_t announce;static void *ctx;
static unsigned sends,closes;static bool fail_send,synchronous;static uint8_t sent[64];static size_t sent_n;
static struct redwood_qrtr_port *openp(redwood_qrtr_receive_t r,redwood_qrtr_server_t s,void *c){receive=r;announce=s;ctx=c;port.live=1;return &port;}
static int lookup(struct redwood_qrtr_port *p,uint32_t id,uint32_t v,uint32_t i){assert(p==&port && id==69 && v==1 && i==0);announce(ctx,true,69,1,0,0,70);return 0;}
static void respond(unsigned msg,unsigned result,unsigned error,bool has_status,uint64_t status){
 struct eq_wlfw_probe *w=ctx;uint8_t b[25]={2,(uint8_t)w->txn,(uint8_t)(w->txn>>8),(uint8_t)msg,0,7,0,2,4,0,(uint8_t)result,0,(uint8_t)error,0};
 size_t n=14;if(has_status){b[5]=18;b[14]=0x10;b[15]=8;for(unsigned i=0;i<8;i++)b[17+i]=(uint8_t)(status>>(i*8));n=25;}
 receive(ctx,0,70,b,n);
}
static int sendp(struct redwood_qrtr_port *p,uint32_t node,uint32_t peer,const void *data,size_t n){assert(p==&port && p->live && node==0 && peer==70 && n<=sizeof(sent));memcpy(sent,data,n);sent_n=n;sends++;if(synchronous)respond(sent[3],0,0,true,2);return fail_send?5:0;}
static void closep(struct redwood_qrtr_port *p){assert(p==&port && p->live);p->live=0;closes++;}
static const struct redwood_qrtr_ops ops={openp,sendp,lookup,closep};
static void start(struct eq_wlfw_probe *w){sends=0;assert(eq_wlfw_start(w,&ops,NULL,NULL));}
static void ready_ind(void){uint8_t b[7]={4,0,0,0x21,0,0,0};receive(ctx,0,70,b,7);}
int main(void){
 struct eq_wlfw_probe w;start(&w);eq_wlfw_poll(&w,0,false);assert(sends==0);eq_wlfw_poll(&w,0,true);
 const uint8_t reg[]={0x10,1,0,1,0x13,1,0,1,0x14,1,0,1,0x15,4,0,0x4c,0x45,0x4e,0x4b,0x19,4,0,1,0,0,0};
 assert(sent_n==33 && sent[3]==0x20 && sent[5]==26 && !memcmp(sent+7,reg,26));
 respond(0x20,0,0,true,4);assert(w.registered && !w.fw_ready && w.fw_status==4);eq_wlfw_poll(&w,100,true);assert(sends==1);
 ready_ind();eq_wlfw_poll(&w,200,true);assert(sends==2 && sent_n==7 && sent[3]==0x24);respond(0x24,0,0,false,0);assert(w.success);eq_wlfw_stop(&w);
 start(&w);synchronous=true;eq_wlfw_poll(&w,0,true);synchronous=false;assert(w.registered && w.fw_ready && !w.pending);eq_wlfw_poll(&w,1,true);assert(sends==2);respond(0x24,1,90,false,0);assert(w.answered && !w.success && w.error==90);eq_wlfw_stop(&w);
 start(&w);eq_wlfw_poll(&w,0,true);respond(0x20,1,16,false,0);eq_wlfw_poll(&w,9000000,true);assert(sends==1 && !w.registered);eq_wlfw_stop(&w);
 start(&w);fail_send=true;for(unsigned i=0;i<10;i++)eq_wlfw_poll(&w,i*2000000ull,true);fail_send=false;assert(sends==3 && w.send_errors==3 && !w.pending);eq_wlfw_stop(&w);
 start(&w);eq_wlfw_poll(&w,0,true);uint8_t malformed[14]={2,1,0,0x20,0,7,0,2,4,0,0,0,0,0};
 for(unsigned n=0;n<14;n++)receive(ctx,0,70,malformed,n);assert(!w.registered && w.pending);
 receive(ctx,1,70,malformed,14);receive(ctx,0,71,malformed,14);malformed[1]=2;receive(ctx,0,70,malformed,14);assert(!w.registered);
 respond(0x24,0,0,false,0);assert(!w.registered);respond(0x20,0,0,false,0);assert(w.registered && !w.status_valid && !w.fw_ready);
 announce(ctx,true,69,1,0,0,70);assert(w.registered);announce(ctx,false,69,1,0,0,70);assert(!w.present && !w.registered);ready_ind();assert(!w.fw_ready);
 announce(ctx,true,69,1,0,0,70);eq_wlfw_poll(&w,50,true);assert(sent[3]==0x20 && sends==2);eq_wlfw_stop(&w);
 assert(closes==5);puts("0164: registration bytes, gating, status/indications, reentrant reply, errors, retries, truncation, identity and restart passed");
}
''')
    exe=root/'test'
    cc=os.environ.get('CC','cc')
    subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-I',str(dev),str(dev/'test.c'),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
