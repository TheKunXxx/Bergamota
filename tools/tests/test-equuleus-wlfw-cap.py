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
 for pre in ['0150','0151','0152','0153','0154','0155','0156','0157','0158','0159','0160','0161','0162','0163']:
  patch=next((repo/'xnu/patches').glob(pre+'-*'))
  subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
  subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
 source=(dev/'mi8_hostsvc.c').read_text();assert 'rmtfs(' not in source
 header=(dev/'mi8_hostsvc.h').read_text();assert 'part_read' not in header and 'rmtfs_phys' not in header

 harness=r"""
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "equuleus_wlfw_probe.h"
struct redwood_qrtr_port {unsigned live;};static struct redwood_qrtr_port p;
static redwood_qrtr_receive_t receiver;static redwood_qrtr_server_t server;static void *context;
static unsigned sends,closes;static bool reentrant,lookup_fail,send_fail;
static uint8_t reply[32];
static unsigned response(unsigned txn,unsigned result,unsigned error){memset(reply,0,sizeof(reply));reply[0]=2;reply[1]=txn;reply[2]=txn>>8;reply[3]=0x24;reply[5]=7;reply[7]=2;reply[8]=4;reply[10]=result;reply[12]=error;return 14;}
static struct redwood_qrtr_port *op(redwood_qrtr_receive_t r,redwood_qrtr_server_t s,void *c){receiver=r;server=s;context=c;p.live=1;return &p;}
static int lookup(struct redwood_qrtr_port *q,uint32_t id,uint32_t v,uint32_t i){assert(q==&p && id==69 && v==1 && !i);if(lookup_fail)return 5;server(context,true,69,1,0,0,74);return 0;}
static int tx(struct redwood_qrtr_port *q,uint32_t node,uint32_t port,const void *data,size_t n){const uint8_t *b=data;assert(q==&p && p.live && !node && port==74 && n==7 && b[0]==0 && b[3]==0x24 && !b[4] && !b[5] && !b[6]);sends++;if(reentrant){unsigned len=response(eq_wlfw_u16(b+1),0,0);receiver(context,0,74,reply,len);}return send_fail?5:0;}
static void closep(struct redwood_qrtr_port *q){assert(q==&p && p.live);q->live=0;closes++;}
static const struct redwood_qrtr_ops ops={op,tx,lookup,closep};
int main(void){
 struct eq_wlfw_probe w;assert(eq_wlfw_start(&w,&ops,NULL,NULL));assert(w.present);eq_wlfw_poll(&w,0,false);assert(!sends);
 reentrant=true;eq_wlfw_poll(&w,0,true);reentrant=false;assert(w.success && w.answered && sends==1);eq_wlfw_poll(&w,9000000,true);assert(sends==1);eq_wlfw_stop(&w);assert(closes==1);
 assert(eq_wlfw_start(&w,&ops,NULL,NULL));eq_wlfw_poll(&w,0,true);unsigned n=response(w.txn,1,16);receiver(&w,0,74,reply,n);assert(w.answered && !w.success && w.error==16);eq_wlfw_stop(&w);
 assert(eq_wlfw_start(&w,&ops,NULL,NULL));eq_wlfw_poll(&w,0,true);n=response(w.txn,0,0);receiver(&w,1,74,reply,n);receiver(&w,0,75,reply,n);reply[1]^=1;receiver(&w,0,74,reply,n);reply[1]^=1;assert(!w.answered && w.rejected==3);
 for(unsigned i=0;i<n;i++)receiver(&w,0,74,reply,i);assert(!w.answered);
 reply[14]=2;reply[15]=4;reply[5]=14;receiver(&w,0,74,reply,21);assert(!w.answered);n=response(w.txn,0,1);receiver(&w,0,74,reply,n);assert(!w.answered);
 uint32_t seed=31;for(unsigned i=0;i<2000;i++){uint8_t b[32];n=response(w.txn,0,0);memcpy(b,reply,n);seed=seed*1664525u+1013904223u;b[seed%n]^=1;receiver(&w,0,74,b,n);w.pending=true;w.answered=w.success=false;}eq_wlfw_stop(&w);
 assert(eq_wlfw_start(&w,&ops,NULL,NULL));sends=0;send_fail=true;eq_wlfw_poll(&w,0,true);eq_wlfw_poll(&w,500,true);assert(sends==1);eq_wlfw_poll(&w,2000000,true);eq_wlfw_poll(&w,4000000,true);eq_wlfw_poll(&w,6000000,true);assert(sends==3 && w.send_errors==3 && !w.pending);send_fail=false;eq_wlfw_stop(&w);
 assert(eq_wlfw_start(&w,&ops,NULL,NULL));eq_wlfw_poll(&w,0,true);server(&w,false,69,1,0,0,74);n=response(w.txn,0,0);receiver(&w,0,74,reply,n);assert(!w.present && !w.answered);eq_wlfw_stop(&w);
 lookup_fail=true;assert(!eq_wlfw_start(&w,&ops,NULL,NULL) && !p.live);
 puts("0163 actual WLFW69 CAP: lookup, UP gate, reentrant success/QMI error, peer/txn/TLV/truncation checks, 2000 mutations, bounded retries and close passed");return 0;
}
"""
 c=dev/'test.c';c.write_text(harness);exe=root/'test'
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-I',str(dev),str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
