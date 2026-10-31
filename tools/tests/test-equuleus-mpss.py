#!/usr/bin/env python3
"""Test patch replay, packed MDT bounds and mocked MPSS/SMP2P failures.

Hardware register semantics and real XNU integration require CI/device tests.
"""
from pathlib import Path
import ast
import ctypes
import random
import struct
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[2]

def materialize(root):
    text = (repo/'xnu/patches/0149-equuleus-mss-mba-bringup.patch').read_text()
    tail = text.split('+++ b/bsd/dev/equuleus_mss.c\n', 1)[1]
    source = '\n'.join(s[1:] for s in tail.splitlines() if s.startswith('+'))+'\n'
    path = root/'bsd/dev/equuleus_mss.c'
    path.parent.mkdir(parents=True)
    path.write_text(source)
    subprocess.run(['git','init','-q',str(root)],check=True)
    patch=repo/'xnu/patches/0150-equuleus-mpss-smp2p-bringup.patch'
    subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
    subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
    return path.read_text()

def metadata():
    b=bytearray(212);b[:7]=b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHIIIIIHHHHHH',b,16,2,164,1,0x8e400000,52,0,0,52,32,3,0,0,0)
    struct.pack_into('<8I',b,52,0,0,0,0,148,0,0x7000000,0)
    struct.pack_into('<8I',b,84,0,148,0,0x95c00000,64,64,0x2200000,0)
    struct.pack_into('<8I',b,116,1,0,0,0x8e400000,16,32,0x8000005,4096)
    return b

with tempfile.TemporaryDirectory(prefix='equuleus-0150-') as tmp:
    root=Path(tmp);source=materialize(root)
    a=source.index('#define MAX_SEGMENTS 48u');b=source.index('bool equuleus_mpss_load(',a)
    parser=source[a:b]
    prefix='''#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#define PAGE_SIZE 16384u
#define MPSS_MEMORY 0x8e400000u
#define MPSS_SIZE 0x07800000u
#define MIN(a,b) ((a)<(b)?(a):(b))
#define say(...) ((void)0)
struct fs_file { uint32_t first,size;bool dir; };
static bool fs_lookup(const char *p,struct fs_file *f) { (void)p;(void)f;return false; }
'''
    c=root/'parser.c';lib=root/'parser.so'
    c.write_text(prefix+'''struct smem_table_entry { uint8_t x[48]; };
struct smem_partition { uint8_t x[32]; };
'''+parser+'\nint check(const uint8_t *p,uint32_t n) { return mpss_validate(p,n,false); }\n')
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-fsanitize=undefined',str(c),'-o',str(lib)],check=True)
    api=ctypes.CDLL(str(lib));api.check.argtypes=[ctypes.c_void_p,ctypes.c_uint32];api.check.restype=ctypes.c_int
    def check(data):
        buf=ctypes.create_string_buffer(bytes(data));return api.check(buf,len(data))
    good=metadata();assert check(good)==1
    for n in range(212):assert check(good[:n])==0,('truncated',n)
    invalid=[]
    for off,fmt,value in [(0,'I',0),(4,'B',2),(5,'B',2),(6,'B',0),(20,'I',0),
                           (28,'I',0xffffffff),(40,'H',0),(42,'H',31),(44,'H',0),(44,'H',65535),
                           (68,'I',147),(100,'I',0),(100,'I',63),(132,'I',33),
                           (136,'I',0x7800001),(128,'I',0xffffffff)]:
        x=bytearray(good);struct.pack_into('<'+fmt,x,off,value);invalid.append(x)
    x=bytearray(good);struct.pack_into('<I',x,128,0x8e3fffff);struct.pack_into('<I',x,140,5);invalid.append(x)
    for i,x in enumerate(invalid):assert check(x)==0,('malformed',i)
    x=bytearray(good);struct.pack_into('<I',x,128,0x1000);assert check(x)==1
    rng=random.Random(150)
    for _ in range(2000):
        x=bytearray(good)
        for _ in range(rng.randrange(1,9)):x[rng.randrange(len(x))]=rng.randrange(256)
        check(x)
    print('0150 replay; valid/relocated MDT; 212 truncations; 17 malformed headers; 2000 mutation smoke cases passed')

    # Reuse the mock hardware harness from 0149 but execute the actual new boot routine.
    tree=ast.parse((repo/'tools/tests/test-equuleus-mss.py').read_text())
    strings={node.targets[0].id:ast.literal_eval(node.value) for node in tree.body
             if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)
             and node.targets[0].id in ('harness','main')}
    harness=strings['harness']
    harness=harness.replace('assert(!strcmp(name,"image/mba.mbn"));','''if (!strcmp(name,"image/modem.mdt")) {
        *size=100;void *p=calloc(1,*size);assert(p);allocations++;return p;
    }
    assert(!strcmp(name,"image/mba.mbn"));''')
    harness=harness.replace('if (scenario==3) return 0;','if (scenario==3 || scenario==17) return 0;')
    extra='''#define MBA_META_OFFSET 0x100000u
static bool mss_full_test;
static unsigned loaded, compares;
static bool mpss_validate(const uint8_t *p,uint32_t n,bool f) { (void)p;(void)n;(void)f;return scenario!=13; }
static bool modem_prepare_smp2p(void) { return scenario!=14; }
static bool equuleus_mpss_load(vm_offset_t r,uint64_t *o) { (void)r;(void)o;loaded++;return scenario!=15; }
static int test_compare(const void *a,const void *b,size_t n) {
    compares++;if((scenario==18 && compares==1)||(scenario==19 && compares==2))return 1;
    return memcmp(a,b,n);
}
'''
    boot=source.split('static void\nmss_run_mba(void)\n',1)[1].split('\n/* Called on the existing',1)[0]
    boot='static void\nmss_run_mba(void)\n'+boot
    boot=boot.replace('memcmp(', 'test_compare(')
    main=strings['main'].replace('scenario=atoi(argv[1]);mss_run_mba();','scenario=atoi(argv[1]);mss_full_test=scenario>=13;mss_run_mba();')
    main=main.replace('    return 0;\n}', '''    if(scenario==13 || scenario==14 || scenario==17 || scenario==18 || scenario==19) {
        assert(q6_boots==0 && loaded==0 && assignments==0);
    }
    if(scenario==15 || scenario==16) { assert(q6_boots==1 && loaded==1 && assignments==4 && halted==3); }
    return 0;
}''')
    c=root/'boot.c';exe=root/'boot';c.write_text(harness+extra+boot+main)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-but-set-variable','-Wno-unused-variable',
                    '-fsanitize=undefined',str(c),'-o',str(exe)],check=True)
    for n in range(20):subprocess.run([str(exe),str(n)],check=True)
    print('20 actual boot-routine MBA/MPSS preflight, readback, failure and cleanup cases passed (mock hardware)')

with tempfile.TemporaryDirectory(prefix='eq-smem-0150-') as tmp:
    root=Path(tmp);source=materialize(root)
    a=source.index('/* 0150 MPSS and SMP2P');b=source.index('#define MAX_SEGMENTS 48u',a)
    helpers=source[a:b]
    prefix=r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
typedef uintptr_t vm_offset_t;
#define VM_WIMG_WCOMB 1
#define VM_PROT_READ 1
#define VM_PROT_WRITE 2
#define MPSS_MEMORY 0x8e400000u
#define MPSS_SIZE 0x07800000u
#define PAGE_SIZE 16384u
#define NSEC_PER_MSEC 1000000
#define NSEC_PER_USEC 1000
#define MIN(a,b) ((a)<(b)?(a):(b))
#define __offsetof(t,m) __builtin_offsetof(t,m)
#define say(...) ((void)0)
#define announce(...) ((void)0)
#define RMB_MBA_STATUS 12u
#define IPC_SMP2P_ADSP (1u<<10)
#define IPC_SMP2P_MODEM (1u<<14)
static uint8_t memory[0x200000],locks[0x8000];
static uint64_t fake_us;
static uintptr_t stop_at,remote_at;
static bool answer_stop;
static unsigned bells;
static vm_offset_t io_map(uint64_t p,size_t n,unsigned f,unsigned prot,bool temp) {
    (void)f;(void)prot;(void)temp;
    return p==0x86000000 && n==sizeof(memory) ? (uintptr_t)memory : 0;
}
static void ml_io_unmap(vm_offset_t a,size_t n) {(void)a;(void)n;}
static vm_offset_t ml_io_map(vm_offset_t p,size_t n) {assert(p==0x1f40000 && n==sizeof(locks));return (uintptr_t)locks;}
static uint32_t rd(vm_offset_t p) {return *(uint32_t *)p;}
static void wr(vm_offset_t p,uint32_t v) {
    assert((p>=(uintptr_t)memory && p<=(uintptr_t)memory+sizeof(memory)-4) ||
           (p>=(uintptr_t)locks && p<=(uintptr_t)locks+sizeof(locks)-4));
    *(uint32_t *)p=v;
    if(p==stop_at && v==1 && answer_stop) *(uint32_t *)remote_at=10;
}
static void settle(void) {}
static void ring(unsigned mask) {(void)mask;bells++;}
static void delay_for_interval(unsigned n,unsigned scale) {(void)n;(void)scale;}
static uint64_t mach_absolute_time(void) {fake_us+=1000;return fake_us*1000;}
static void absolutetime_to_nanoseconds(uint64_t t,uint64_t *n) {*n=t;}
#define strlcpy host_strlcpy
static size_t host_strlcpy(char *d,const char *s,size_t n) {
    size_t len=strlen(s);if(n){size_t take=len<n-1?len:n-1;memcpy(d,s,take);d[take]=0;}return len;
}
'''
    main=r'''
static struct smem_partition *part(void) {return (void *)(memory+0xb9000);}
static void reset(void) {
    memset(memory,0,sizeof(memory));memset(locks,0,sizeof(locks));fake_us=0;bells=0;answer_stop=false;stop_at=remote_at=0;
    smem=NULL;mutex_base=0;our_item=0;smp2p_agreed=smp2p_restart_acks=smp2p_restart_acked=false;
    struct smem_table *t=(void *)(memory+sizeof(memory)-0x1000);memcpy(t->magic,"$TOC",4);t->version=1;t->count=15;
    struct smem_table_entry *e=(void *)(t+1);e+=10;e->offset=0xb9000;e->size=0x7c000;e->host0=0;e->host1=1;e->cacheline=64;
    struct smem_partition *p=part();memcpy(p->magic,"$PRT",4);p->host0=0;p->host1=1;p->size=0x7c000;p->free_uncached=32;p->free_cached=p->size;
}
static struct smp2p *remote(void) {
    uint32_t size=0;assert(lock_take());assert(item_make_locked(0xb9000,435,344));lock_give();
    uint32_t at=item_find(0xb9000,64,435,&size);assert(at && size==344);
    struct smp2p *p=(void *)(memory+at);memset(p,0,sizeof(*p));p->magic=SMP2P_MAGIC;p->version=0x101;
    p->local=1;p->remote=0;p->total=16;p->valid=1;strlcpy(p->entry[0].name,"slave-kernel",16);
    remote_at=(uintptr_t)&p->entry[0].value;return p;
}
int main(void) {
    struct smp2p *r;uint32_t n=0,cl=0,size=0;
    reset();assert(!smem_peek(UINT64_MAX,&n,4));assert(smem_partition(0,1,&cl,&size)==0xb9000 && cl==64);
    assert(modem_prepare_smp2p());assert(our_item && item_find(0xb9000,64,479,&size) && size==16384);
    r=remote();r->entry[0].value=2;assert(modem_watch(1,10));
    stop_at=(uintptr_t)memory+our_item+36;answer_stop=true;assert(dsp_ask_to_stop(50));assert(*(uint32_t *)stop_at==0);
    reset();assert(modem_prepare_smp2p());r=remote();r->entry[0].value=2;stop_at=(uintptr_t)memory+our_item+36;
    assert(!dsp_ask_to_stop(10) && *(uint32_t *)stop_at==0);
    reset();assert(modem_prepare_smp2p());r=remote();r->entry[0].value=1;assert(!modem_watch(1,10));
    reset();assert(modem_prepare_smp2p());r=remote();assert(!modem_watch(1,10));
    reset();r=remote();r->entry[0].value=2;assert(!modem_prepare_smp2p());
    reset();part()->free_uncached=48;assert(!modem_prepare_smp2p());
    reset();assert(modem_prepare_smp2p());r=remote();r->flags=1;dsp_listen(r);assert(*(uint32_t *)(memory+our_item+16)==2);
    r->flags=0;dsp_listen(r);assert(*(uint32_t *)(memory+our_item+16)==0);
    reset();assert(modem_prepare_smp2p());r=remote();r->version=1;r->flags=1;dsp_listen(r);
    assert(*(uint32_t *)(memory+our_item+4)==1 && *(uint32_t *)(memory+our_item+16)==0);
    return 0;
}
'''
    c=root/'smem.c';exe=root/'smem';c.write_text(prefix+helpers+main)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-parameter','-Wno-format','-Wno-unused-but-set-variable','-Wno-unused-variable',
                    '-fsanitize=undefined',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
    print('Actual SMEM/SMP2P bounds, allocation, READY/fatal/timeout, STOP_ACK and restart-negotiation cases passed (mock hardware)')

with tempfile.TemporaryDirectory(prefix='eq-loader-0150-') as tmp:
    root=Path(tmp);source=materialize(root)
    a=source.index('#define MAX_SEGMENTS 48u');b=source.index('bool equuleus_mpss_load(',a)
    parser=source[a:b]
    a=source.index('bool\nequuleus_mpss_load(');b=source.index('\nstatic bool mss_full_test;',a)
    loader=source[a:b]
    prefix=r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
typedef uintptr_t vm_offset_t;
#define PAGE_SIZE 16384u
#define MPSS_MEMORY 0x8e400000u
#define MPSS_SIZE 0x07800000u
#define MBA_MEMORY 0x96900000u
#define RMB_MBA_STATUS 12u
#define Z_WAITOK 1
#define MIN(a,b) ((a)<(b)?(a):(b))
#define say(...) ((void)0)
#define announce(...) ((void)0)
struct smem_table_entry {uint8_t x[48];};
struct smem_partition {uint8_t x[32];};
struct fs_file {uint32_t first,size;bool dir;};
static int scenario,allocations,lookups,assigned,writes,copies,stops;
static uint32_t command,length;
static uint8_t copied[32];
static const uint8_t packed[] = {
'''+','.join(str(x) for x in metadata())+r'''
};
static bool fs_lookup(const char *name,struct fs_file *f) {
    assert(!strcmp(name,"image/modem.b02"));lookups++;f->first=2;f->size=16;f->dir=false;
    if(scenario==7 && lookups>1) f->size=15;
    return true;
}
static uint8_t *fs_slurp(const char *name,uint32_t *size) {
    assert(!strcmp(name,"image/modem.mdt"));if(scenario==1) return NULL;
    *size=sizeof(packed);uint8_t *p=malloc(*size);assert(p);memcpy(p,packed,*size);allocations++;
    if(scenario==2) { p[0]=0; }
    return p;
}
static void *kalloc_data(size_t size,unsigned flags) {
    (void)flags;if(scenario==6)return NULL;void *p=malloc(size);assert(p);allocations++;return p;
}
static void kfree_data(void *p,size_t n) {(void)n;free(p);allocations--;}
static int fs_file_read(const struct fs_file *f,uint64_t at,void *out,uint64_t n) {
    assert(f->size==16 && at==0 && n==16);if(scenario==8)return 5;memset(out,0x6a,n);return 0;
}
static uint64_t now_us(void) {return 0;}
static bool assign_mem(const char *name,uint32_t pa,uint32_t size,uint64_t *owners,bool local,bool remote) {
    assert(!strcmp(name,"mpss") && pa==MPSS_MEMORY && size==MPSS_SIZE);assigned++;
    if((scenario==4 && assigned==1)||(scenario==5 && assigned==2)||(scenario==11 && assigned==3))return false;
    *owners=(local?8u:0u)|(remote?0x8000u:0u);return true;
}
static bool put_phys(uint64_t pa,const void *p,uint32_t n) {
    assert(pa==MPSS_MEMORY && n==32);copies++;if(scenario==9)return false;memcpy(copied,p,n);return true;
}
static uint32_t rd(vm_offset_t pa) {
    if(pa==0x4180000u+0x18)return length;
    if(pa==0x4180000u+12)return scenario==10 && length ? (uint32_t)-1 : 4;
    return 0;
}
static void wr(vm_offset_t pa,uint32_t value) {
    writes++;if(pa==0x4180000u+8)command=value;if(pa==0x4180000u+0x18)length=value;
}
static int32_t mba_wait(vm_offset_t r,int32_t want,uint32_t ms) {
    assert(r==0x4180000u);(void)ms;
    if(want==3)return scenario==3?-1:3;
    assert(want==4);return scenario==12?0:4;
}
static bool modem_watch(uint32_t seconds,uint32_t after_ms) {assert(seconds==15 && after_ms==4000);return scenario!=13;}
static bool dsp_ask_to_stop(uint32_t ms) {assert(ms==5000);stops++;return true;}
static uint32_t __attribute__((unused)) adsp_item(uint32_t item,uint32_t *n) {(void)item;*n=0;return 0;}
#define ITEM_SMP2P_THEIRS_ALT 435
#define ITEM_GLINK_DESCRIPTOR 478
#define ITEM_GLINK_FIFO 479
'''
    main=r'''
int main(int argc,char **argv) {
    assert(argc==2);scenario=atoi(argv[1]);uint64_t owners=0x8000;
    bool ok=equuleus_mpss_load(0x4180000u,&owners);assert(allocations==0);
    assert(ok==(scenario==0));
    if(scenario==0) {
        assert(copies==1 && command==2 && length==32 && assigned==3 && owners==0x8000 && stops==1);
        for(unsigned i=0;i<32;i++)assert(copied[i]==(i<16?0x6a:0));
    }
    if(scenario==1 || scenario==2)assert(writes==0 && assigned==0 && copies==0 && stops==0);
    if(scenario==3)assert(assigned==0 && copies==0);
    if(scenario>=4 && scenario<=8)assert(copies==0);
    if(scenario==9)assert(copies==1 && length==0);
    if(scenario>=10)assert(copies==1);
    return 0;
}
'''
    c=root/'loader.c';exe=root/'loader';c.write_text(prefix+parser+loader+main)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-but-set-variable','-Wno-unused-variable',
                    '-fsanitize=undefined',str(c),'-o',str(exe)],check=True)
    for n in range(14):subprocess.run([str(exe),str(n)],check=True)
    print('14 actual segment-loader metadata/auth/ownership/read/map/READY failure cases and BSS-zeroing checks passed (mock hardware)')
