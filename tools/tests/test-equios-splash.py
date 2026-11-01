#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile,os,struct,hashlib
repo=Path(__file__).resolve().parents[2];shim=repo/'shim';asset=shim/'assets/equios-splash.rle';b=asset.read_bytes()
assert hashlib.sha256(b).hexdigest()==asset.with_suffix('.sha256').read_text().split()[0]
assert struct.unpack_from('<4sHHHH',b)==(b'EQSP',1080,2248,256,0)
palette=[struct.unpack_from('<I',b,12+4*i)[0]&0xffffff for i in range(256)];visible=[];pos=0
for at in range(1036,len(b),3):
 run,index=struct.unpack_from('<HB',b,at)
 if palette[index]:visible.extend(range(pos,pos+run))
 pos+=run
assert pos==1080*2248
assert min(p%1080 for p in visible)>=80 and max(p%1080 for p in visible)<1000
assert min(p//1080 for p in visible)>=170 and max(p//1080 for p in visible)<2118
with tempfile.TemporaryDirectory() as td:
 root=Path(td);c=root/'test.c';exe=root/'test';c.write_text(r'''
#include <assert.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#define BOARD_EQUULEUS
#define EQUULEUS_SPLASH
#include "equios_splash.c"
volatile uint32_t *con_fb;
int main(void){
 const unsigned pitch=1087,h=2248;size_t pixels=(size_t)pitch*h;uint32_t *frame=malloc((pixels+16)*4);assert(frame);for(size_t i=0;i<pixels+16;i++)frame[i]=0x12345678;
 size_t n=(uintptr_t)equios_splash_end-(uintptr_t)equios_splash_begin;assert(equios_splash_render(frame,1080,h,pitch,equios_splash_begin,n));
 for(unsigned y=0;y<h;y++)for(unsigned x=1080;x<pitch;x++)assert(frame[y*pitch+x]==0x12345678);for(unsigned i=0;i<16;i++)assert(frame[pixels+i]==0x12345678);
 uint8_t *copy=malloc(n);assert(copy);memcpy(copy,equios_splash_begin,n);unsigned locations[]={0,4,6,8,10};for(unsigned j=0;j<5;j++){copy[locations[j]]^=1;frame[0]=0x12345678;assert(!equios_splash_render(frame,1080,h,pitch,copy,n) && frame[0]==0x12345678);copy[locations[j]]^=1;}
 assert(!equios_splash_render(frame,1080,h,pitch,copy,n-1));copy[1036]=copy[1037]=0;assert(!equios_splash_render(frame,1080,h,pitch,copy,n));
 con_fb=frame;assert(equios_splash_show());free(copy);free(frame);puts("EquiOS actual embedded splash:1080x2248, safe notch/frame bounds, stride guards and malformed-stream refusal passed");return 0;
}
''');subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-I',str(shim),str(c),'-o',str(exe)],cwd=shim,check=True);subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
assert 'delay_ms(3000);' in (shim/'shim.c').read_text()
print('3-second show gate checked; actual AArch64 link is checked by shim/build.sh on build host')
