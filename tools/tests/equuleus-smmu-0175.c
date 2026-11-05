#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
typedef uintptr_t vm_offset_t;
struct eq_wlfw_probe {
 vm_offset_t wlan_smmu;void (*log)(void*,const char*,...);void *ctx;
 bool msa_assigned,msa_ready_ack,msa_layout_ok;
};
#define EQ_WLFW_MSA_BASE 0xa8300000ull
#define EQ_WLFW_MSA_BYTES 0x100000u
#define NSEC_PER_USEC 1000
#define KMA_KOBJECT 1
#define KMA_ZERO 2
#define KMA_DATA 4
#define VM_KERN_MEMORY_IOKIT 1
#define KERN_SUCCESS 0
static int kernel_map;
static uint32_t regs[0x80000/4];
static unsigned writes,failreg,allocation_fails,badpa,tlb_busy,fail_publish,fail_detach,fail_s2cr;
static unsigned char pool[0x4000] __attribute__((aligned(0x4000)));
static unsigned at(vm_offset_t p){assert(p>=0x15000000ul && p<0x15080000ul);assert(!(p&3));return (p-0x15000000ul)/4;}
static uint32_t rd(vm_offset_t p){return regs[at(p)];}
static void wr(vm_offset_t p,uint32_t v){
 writes++;
 if(fail_s2cr && p==0x15000c18ul && v==3)return;
 if(failreg && p==0x15043000ul+failreg)return;
 if(p==0x15000800ul+6*4 && ((v && fail_publish) || (!v && fail_detach)))return;
 regs[at(p)]=v;
 if(p==0x150437f0)regs[at(0x150437f4)]=tlb_busy;
}
static vm_offset_t ml_io_map(vm_offset_t p,unsigned n){assert(n==0x1000);return p;}
static void delay_for_interval(unsigned n,unsigned scale){assert(n==10 && scale==1000);}
static int kmem_alloc(int map,vm_offset_t *va,unsigned n,unsigned flags,unsigned tag){
 (void)map;(void)flags;(void)tag;assert(n==sizeof(pool));
 if(allocation_fails)return 1;
 memset(pool,0,sizeof(pool));*va=(vm_offset_t)pool;return 0;
}
uint64_t kvtophys(vm_offset_t va){
 assert(va>=(vm_offset_t)pool && va<(vm_offset_t)pool+sizeof(pool));
 return (badpa?1ull<<40:0x100000000ull)+(va-(vm_offset_t)pool);
}
#include "smmu175host.h"
static void reset(void){
 memset(regs,0,sizeof(regs));writes=failreg=allocation_fails=badpa=tlb_busy=fail_publish=fail_detach=fail_s2cr=0;
 eqs_attempted=eqs_active=false;eqs_last_fault=0;
 regs[at(0x15000000)]=0x250406;
 regs[at(0x15000020)]=0x4c017e4c;
 regs[at(0x15000024)]=0x5000002d;
 regs[at(0x15000028)]=0x5555;
 regs[at(0x15043000)]=0xe0;regs[at(0x15043058)]=0x400;
 regs[at(0x1500100c)]=0x10000;regs[at(0x1500180c)]=1;
 regs[at(0x15043010)]=0x40018077;
 for(unsigned i=0;i<6;i++){regs[at(0x15000800+i*4)]=0x80000010+i;regs[at(0x15000c00+i*4)]=i%3;}
}
static bool mapped(uint64_t pa){
 uint64_t *a=(uint64_t*)pool,*b=(uint64_t*)(pool+0x1000),*c=(uint64_t*)(pool+0x2000);
 return (a[(pa>>30)&511]&1) && (b[(pa>>21)&511]&1) && (c[(pa>>12)&511]&1);
}
int main(void){
 struct eq_wlfw_probe w={.wlan_smmu=0x15000000,.msa_assigned=true,.msa_ready_ack=true,.msa_layout_ok=true};
 reset();assert(eq_wlfw_smmu_translate(&w));assert(eqs_active);
 assert(rd(0x15000818)==0x80010040 && rd(0x15000c18)==3);
 assert(rd(0x15043000)==0x1127);
 for(uint64_t pa=EQ_WLFW_MSA_BASE;pa<EQ_WLFW_MSA_BASE+EQ_WLFW_MSA_BYTES;pa+=4096){assert(mapped(pa));assert((((uint64_t*)(pool+0x2000))[(pa>>12)&511]&0x0000fffffffff000ull)==pa);}
 assert(!mapped(EQ_WLFW_MSA_BASE-4096));assert(!mapped(EQ_WLFW_MSA_BASE+EQ_WLFW_MSA_BYTES));
 unsigned entries=0;for(unsigned i=0;i<512;i++){uint64_t p=((uint64_t*)(pool+0x2000))[i];if(p){entries++;assert((p&(3ull<<53))==(3ull<<53));}}
 assert(entries==256);unsigned savedwrites=writes;assert(eq_wlfw_smmu_translate(&w));assert(writes==savedwrites);
 regs[at(0x15043058)]|=2;eqs_watch(&w);assert(eqs_last_fault==2);
 reset();w.msa_assigned=false;assert(!eq_wlfw_smmu_translate(&w) && !writes);w.msa_assigned=true;
 reset();regs[at(0x15000800)]=0x80000040;assert(!eq_wlfw_smmu_translate(&w) && !writes);
 reset();regs[at(0x15000c00)]=3;assert(!eq_wlfw_smmu_translate(&w) && !writes);
 reset();allocation_fails=1;assert(!eq_wlfw_smmu_translate(&w) && !writes);
 reset();badpa=1;assert(!eq_wlfw_smmu_translate(&w) && !writes);
 reset();failreg=0x30;assert(!eq_wlfw_smmu_translate(&w));assert(rd(0x15043000)==0xe0 && !rd(0x15000818) && !rd(0x15000c18));
 reset();tlb_busy=1;assert(!eq_wlfw_smmu_translate(&w));assert(rd(0x15043000)==0xe0 && !rd(0x15000818));
 reset();fail_s2cr=1;assert(!eq_wlfw_smmu_translate(&w));assert(rd(0x15043000)==0xe0 && !rd(0x15000818));
 reset();fail_publish=1;assert(!eq_wlfw_smmu_translate(&w));assert(rd(0x15043000)==0xe0 && !rd(0x15000c18));
 assert(rd(0x15043010)==0x40018077 && !rd(0x15043020));
 puts("0175 table bounds, readback, collision, allocation, TLB timeout and rollback: PASS");
}
