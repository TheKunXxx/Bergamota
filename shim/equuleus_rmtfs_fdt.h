/* SPDX-License-Identifier: MIT
 * Bounded FDT v17 range check; reject unsupported address-cell layouts.
 */
#pragma once
#include <stddef.h>
#include "equuleus_rmtfs_contract.h"
static uint32_t eq_be32(const uint8_t *p)
{ return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3]; }
static uint64_t eq_be64(const uint8_t *p)
{ return (uint64_t)eq_be32(p)<<32 | eq_be32(p+4); }
static int eq_text(const uint8_t *p,size_t n,const char *s)
{
 size_t i=0;while(s[i]) {if(i>=n || p[i]!=(uint8_t)s[i])return 0;i++;}
 return i<n && p[i]==0;
}
static int eq_fdt_range_usable(const uint8_t *f,size_t available,uint64_t base,uint64_t span)
{
 uint32_t total,off,sz,strings,ss,res;size_t at,end;
 unsigned depth=0,root_ac=2,root_sc=1,res_ac=2,res_sc=1;
 int memory=0,reserved=0,inside=0,saw_end=0;
 if (!span || base>UINT64_MAX-span || !f || available<40 || eq_be32(f)!=0xd00dfeedu) return 0;
 total=eq_be32(f+4);off=eq_be32(f+8);strings=eq_be32(f+12);res=eq_be32(f+16);
 ss=eq_be32(f+32);sz=eq_be32(f+36);
 if (total>available || total<40 || total>0x1000000 || eq_be32(f+20)!=17 ||
     off<40 || off%4 || strings<40 || res<40 || res%8 ||
     off>total || sz>total-off || strings>total || ss>total-strings || res>total) return 0;
 /* Reject colliding header blocks and an unterminated reserve map. */
 if (eq_rmt_overlap(off,sz,strings,ss)) return 0;
 for(at=res;;at+=16) {
  if(at>total || total-at<16 || eq_rmt_overlap(at,16,off,sz) || eq_rmt_overlap(at,16,strings,ss))return 0;
  uint64_t a=eq_be64(f+at),n=eq_be64(f+at+8);
  if(!a && !n)break;
  if(eq_rmt_overlap(base,span,a,n))return 0;
 }
 at=off;end=(size_t)off+sz;
 while(at<end) {
  if(end-at<4)return 0;
  uint32_t token=eq_be32(f+at);at+=4;
  if(token==1) {
   size_t name=at;while(at<end && f[at])at++;
   if(at==end || ++depth>32)return 0;
   if(depth==2) {
    memory=eq_text(f+name,at-name+1,"memory") || (at-name>=7 && f[name]=='m' && f[name+1]=='e' && f[name+2]=='m' && f[name+3]=='o' && f[name+4]=='r' && f[name+5]=='y' && f[name+6]=='@');
    reserved=eq_text(f+name,at-name+1,"reserved-memory");
    if(reserved){res_ac=root_ac;res_sc=root_sc;}
   }
   at=(at+4)&~(size_t)3;if(at>end)return 0;
  } else if(token==2) {
   if(!depth)return 0;
   if(depth==2)memory=reserved=0;
   depth--;
  } else if(token==3) {
   if(!depth || end-at<8)return 0;
   uint32_t n=eq_be32(f+at),no=eq_be32(f+at+4);at+=8;
   if(n>end-at || no>=ss)return 0;
   size_t ne=no;while(ne<ss && f[strings+ne])ne++;
   if(ne==ss)return 0;
   const uint8_t *pn=f+strings+no,*v=f+at;
   if((depth==1 || (depth==2 && reserved)) && (eq_text(pn,ne-no+1,"#address-cells") || eq_text(pn,ne-no+1,"#size-cells"))) {
    if(n!=4)return 0;
    unsigned value=eq_be32(v);
    if(depth==1){if(eq_text(pn,ne-no+1,"#address-cells"))root_ac=value;else root_sc=value;}
    else{if(eq_text(pn,ne-no+1,"#address-cells"))res_ac=value;else res_sc=value;}
   }
   if(eq_text(pn,ne-no+1,"reg") && ((depth==2 && memory) || (depth==3 && reserved))) {
    if((depth==2?(root_ac!=2 || root_sc!=2):(res_ac!=2 || res_sc!=2)) || !n || n%16)return 0;
    for(unsigned i=0;i<n;i+=16) {
     uint64_t a=eq_be64(v+i),s=eq_be64(v+i+8);
     if(a>UINT64_MAX-s)return 0;
     if(depth==2){if(a<=base && s>=span && base-a<=s-span)inside=1;}
     else if(eq_rmt_overlap(base,span,a,s))return 0;
    }
   }
   at=(at+n+3)&~(size_t)3;if(at>end)return 0;
  } else if(token==9) {if(depth)return 0;saw_end=1;break;}
  else if(token!=4)return 0;
 }
 return saw_end && inside && root_ac==2 && root_sc==2;
}

static int eq_rmt_fdt_usable(const uint8_t *f,size_t available)
{
 return eq_fdt_range_usable(f,available,EQ_RMT_POOL,EQ_RMT_SPAN);
}
