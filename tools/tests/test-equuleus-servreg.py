#!/usr/bin/env python3
"""Replay 0154 and compile the actual QMI client against a deterministic QRTR peer."""
from pathlib import Path
import subprocess, tempfile, os
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as td:
 root=Path(td);dev=root/'bsd/dev';dev.mkdir(parents=True)
 tail=(repo/'xnu/patches/0149-equuleus-mss-mba-bringup.patch').read_text().split('+++ b/bsd/dev/equuleus_mss.c\n',1)[1]
 (dev/'equuleus_mss.c').write_text('\n'.join(l[1:] for l in tail.splitlines() if l.startswith('+'))+'\n')
 conf=root/'bsd/conf/files';conf.parent.mkdir(parents=True)
 conf.write_text(''.join('fixture/prefix%u.c\tstandard\n' % i for i in range(117))+'bsd/dev/beryllium_wlan.c\t\tstandard\nbsd/dev/equuleus_mss.c\t\tstandard\nbsd/dev/beryllium_bt_hci.c\t\tstandard\n'+''.join('fixture/suffix%u.c\tstandard\n' % i for i in range(12)))
 subprocess.run(['git','init','-q',td],check=True)
 for pre in ['0150','0151','0152','0153','0154']:
  patch=next((repo/'xnu/patches').glob(pre+'-*'))
  subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
  subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
 harness=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "equuleus_servreg.c"
struct redwood_qrtr_port {int open;};
static struct redwood_qrtr_port handle;
static redwood_qrtr_receive_t receiver;static redwood_qrtr_server_t server;
static void *context;static uint8_t sent[64];static size_t sent_size;
static unsigned sends,closes,lookups;static bool synchronous;static int send_error,lookup_error,open_error;
static struct redwood_qrtr_port *open_port(redwood_qrtr_receive_t r,redwood_qrtr_server_t v,void *c) {
 receiver=r;server=v;context=c;handle.open=1;return open_error?NULL:&handle;
}
static unsigned response(uint8_t *p,uint16_t txn,uint16_t msg,uint16_t result,uint16_t error,bool state,uint32_t value) {
 memset(p,0,64);p[0]=2;sr_put16(p+1,txn);sr_put16(p+3,msg);
 uint8_t v[4];sr_put16(v,result);sr_put16(v+2,error);
 unsigned n=sr_tlv(p,7,2,v,4);
 if(state) {for(unsigned i=0;i<4;i++)v[i]=(uint8_t)(value>>(8*i));n=sr_tlv(p,n,0x10,v,4);}
 sr_put16(p+5,(uint16_t)(n-7));return n;
}
static int send_packet(struct redwood_qrtr_port *p,uint32_t node,uint32_t port,const void *d,size_t n) {
 assert(p==&handle && handle.open && node==0 && port==1 && n<=64);
 memcpy(sent,d,n);sent_size=n;sends++;
 if(synchronous) {uint8_t reply[64];unsigned size=response(reply,sr_u16(sent+1),sr_u16(sent+3),0,0,true,SR_UP);receiver(context,0,1,reply,size);}
 return send_error;
}
static int lookup(struct redwood_qrtr_port *p,uint32_t service,uint32_t version,uint32_t instance) {
 assert(p==&handle && service==66 && version==1 && instance==180);lookups++;
 server(context,true,66,1,180,0,1);return lookup_error;
}
static void close_port(struct redwood_qrtr_port *p) {assert(p==&handle && handle.open);handle.open=0;closes++;}
static const struct redwood_qrtr_ops ops={open_port,send_packet,lookup,close_port};
static struct equuleus_servreg fresh(void) {
 struct equuleus_servreg s={0};return s;
}
static void start(struct equuleus_servreg *s) {assert(equuleus_servreg_start(s,&ops,NULL,NULL)==0);assert(s->bound && s->node==0);}
static unsigned indication(uint8_t *p,uint32_t state,uint16_t txn) {
 memset(p,0,64);p[0]=4;sr_put16(p+3,SR_INDICATION);uint8_t v[4];
 for(unsigned i=0;i<4;i++)v[i]=(uint8_t)(state>>(8*i));
 unsigned n=sr_tlv(p,7,1,v,4);n=sr_tlv(p,n,2,sr_path,sizeof(sr_path)-1);
 sr_put16(v,txn);n=sr_tlv(p,n,3,v,2);sr_put16(p+5,(uint16_t)(n-7));return n;
}
int main(void) {
 uint8_t packet[64],copy[64];unsigned n;struct equuleus_servreg s=fresh();start(&s);
 equuleus_servreg_poll(&s,100);assert(s.attempts==1 && s.reg_txn);
 /* Exact donor encoding: standalone string has no nested length or NUL. */
 assert(sent_size==31 && sent[0]==0 && sr_u16(sent+3)==0x20 && sr_u16(sent+5)==24);
 assert(sent[7]==1 && sr_u16(sent+8)==1 && sent[10]==1);
 assert(sent[11]==2 && sr_u16(sent+12)==17 && !memcmp(sent+14,"msm/modem/wlan_pd",17));
 uint16_t transaction=s.reg_txn;
 n=response(packet,transaction,SR_REGISTER,0,0,true,SR_UP);
 unsigned rejected=s.rejected;
 receiver(context,1,1,packet,n);receiver(context,0,2,packet,n);assert(s.rejected==rejected+2 && !s.registered);
 sr_put16(packet+1,transaction+1);receiver(context,0,1,packet,n);assert(!s.registered);
 sr_put16(packet+1,transaction);
 for(unsigned i=0;i<n;i++)receiver(context,0,1,packet,i);
 assert(!s.registered && s.reg_txn==transaction);
 /* Duplicate result and malformed state are not partial successes. */
 memcpy(copy,packet,n);unsigned extra=sr_tlv(copy,n,2,packet+10,4);sr_put16(copy+5,extra-7);
 receiver(context,0,1,copy,extra);assert(!s.registered);
 memcpy(copy,packet,n);copy[15]=3;receiver(context,0,1,copy,n);assert(!s.registered);
 receiver(context,0,1,packet,n);assert(s.registered && s.up && !s.reg_txn);
 /* Correct and wrong-path indications; no send inside a callback. */
 n=indication(packet,0,0x1234);unsigned before=sends;
 memcpy(copy,packet,n);copy[17]='x';receiver(context,0,1,copy,n);assert(s.up && !s.count);
 receiver(context,0,1,packet,n);assert(!s.up && s.count==1 && sends==before);
 receiver(context,0,1,packet,n);assert(s.count==1);
 equuleus_servreg_poll(&s,200);assert(sr_u16(sent+3)==SR_ACK && s.ack_txn && !s.count);
 assert(sent[7]==1 && sr_u16(sent+8)==17 && !memcmp(sent+10,sr_path,17));
 assert(sent[27]==2 && sr_u16(sent+28)==2 && sr_u16(sent+30)==0x1234 && sent_size==32);
 n=response(packet,s.ack_txn,SR_ACK,0,0,false,0);receiver(context,0,1,packet,n);
 assert(!s.ack_txn && s.acknowledgements==1);
 /* No overflow on flood, finite send budget, each indication validated. */
 for(unsigned i=0;i<9;i++) {n=indication(packet,SR_UP,(uint16_t)i);receiver(context,0,1,packet,n);}
 assert(s.count==8);
 for(unsigned i=0;i<80;i++)equuleus_servreg_poll(&s,300+3000000ull*i);
 assert(s.sends<=32 && s.attempts<=5);
 server(context,false,66,1,180,0,2);assert(s.bound);
 server(context,false,66,1,180,0,1);assert(!s.bound && !s.up && !s.registered && !s.count && !s.ack_txn);
 equuleus_servreg_stop(&s);assert(!s.port && closes==1);
 /* Error 9 never counts as registered. Exactly five attempts on silence/error. */
 s=fresh();start(&s);
 for(unsigned i=0;i<10;i++) {
  equuleus_servreg_poll(&s,1+3000000ull*i);
  if(s.reg_txn) {n=response(packet,s.reg_txn,SR_REGISTER,1,9,false,0);receiver(context,0,1,packet,n);}
 }
 assert(s.attempts==5 && !s.registered && !s.up);
 equuleus_servreg_stop(&s);
 /* Synchronous response during send and send error after callback. */
 s=fresh();start(&s);synchronous=true;send_error=-5;
 equuleus_servreg_poll(&s,1);assert(s.registered && s.up && !s.reg_txn);
 equuleus_servreg_stop(&s);synchronous=false;send_error=0;
 /* An indication newer than an outstanding registration response wins. */
 s=fresh();start(&s);equuleus_servreg_poll(&s,1);transaction=s.reg_txn;
 n=indication(packet,0,5);receiver(context,0,1,packet,n);
 n=response(packet,transaction,SR_REGISTER,0,0,true,SR_UP);receiver(context,0,1,packet,n);
 assert(s.registered && !s.up);
 /* Endpoint replacement rejects old responses; total retry budget preserved. */
 server(context,false,66,1,180,0,1);server(context,true,66,1,180,0,1);
 equuleus_servreg_poll(&s,2);assert(s.reg_txn!=transaction);
 receiver(context,0,1,packet,n);assert(!s.registered);
 /* Mutation smoke tests on actual parser, with a fresh bound client each time. */
 uint32_t seed=7;
 for(unsigned k=0;k<4000;k++) {
  struct equuleus_servreg m={0};m.bound=true;m.node=0;m.remote=1;m.attempts=1;m.reg_txn=1;
  n=indication(packet,SR_UP,5);memcpy(copy,packet,n);
  seed=seed*1664525u+1013904223u;copy[seed%n]^=(uint8_t)(1+(seed>>16));
  sr_receive(&m,0,1,copy,n);assert(m.count<=8);
 }
 equuleus_servreg_stop(&s);
 lookup_error=-7;s=fresh();assert(equuleus_servreg_start(&s,&ops,NULL,NULL)==-7 && !s.port);lookup_error=0;
 open_error=1;s=fresh();assert(equuleus_servreg_start(&s,&ops,NULL,NULL)!=0 && !s.port);
 puts("Actual servreg client: wire encoding, peer/transaction checks, truncation/TLV rejection, UP/DOWN, ACK queue, retry/send bounds, reentrant responses, removal and 4000 mutations passed");
 return 0;
}
'''
 c=dev/'test.c';c.write_text(harness);exe=root/'test'
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(dev),str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
subprocess.run(['python3',str(repo/'tools/tests/test-equuleus-glink.py')],check=True,env={**os.environ,'EQUULEUS_TEST_0154':'1'})
