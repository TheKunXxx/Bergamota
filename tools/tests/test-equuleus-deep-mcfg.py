#!/usr/bin/env python3
"""Replay through 0161 and test actual FAT16 firmware lookup and TFTP aliases."""
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
 for pre in ['0150','0151','0152','0153','0154','0155','0156','0157','0158','0159','0160','0161']:
  patch=next((repo/'xnu/patches').glob(pre+'-*'))
  subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
  subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
 source=(dev/'mi8_hostsvc.c').read_text();assert 'rmtfs(' not in source
 header=(dev/'mi8_hostsvc.h').read_text();assert 'part_read' not in header and 'rmtfs_phys' not in header

 source=(dev/'equuleus_mss.c').read_text()
 fs_code=source[source.index('static uint32_t\nfs_next('):source.index('/* The whole of a small file')]
 fw_code=source[source.index('static bool eq_firmware_path'):source.index('static int eq_host_publish')]
 harness=r"""
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define MIN(a,b) ((a)<(b)?(a):(b))
#define Z_WAITOK 0
static unsigned allocations;static bool read_fail,mount_ok=true;
static void *kalloc_data(size_t n,unsigned flags){(void)flags;void *p=calloc(1,n);if(p)allocations++;return p;}
static void kfree_data(void *p,size_t n){(void)n;if(p){assert(allocations);allocations--;free(p);}}
static void say(const char *fmt,...){(void)fmt;}
static uint8_t disk[65536];static uint16_t fat[128];
static struct {bool ok;uint32_t spc,cluster_bytes,root_bytes,clusters;uint64_t fat_off,root_off,data_off;uint16_t *fat;uint32_t fat_bytes;} fs;
struct fs_file {uint32_t first,size;bool dir;};
static bool fs_mount(void){return mount_ok;}
static int fs_read(uint64_t off,void *out,uint64_t n){if(read_fail || off>sizeof(disk) || n>sizeof(disk)-off)return EIO;memcpy(out,disk+off,n);return 0;}
"""+fs_code+fw_code+r"""
#define MI8_GLINK_HOST_TEST
#include "mi8_hostsvc.c"
static void entry(unsigned dir,unsigned at,const char *name,unsigned cluster,unsigned size,bool isdir){
 uint8_t *e=disk+(dir?fs_cluster_off(dir):fs.root_off)+at*32;fs_name83(name,e);e[11]=isdir?16:32;e[26]=cluster;e[27]=cluster>>8;for(unsigned i=0;i<4;i++)e[28+i]=size>>(8*i);
}
static const char *observed[]={"image/modem_pr/mcfg/configs/mcfg_hw/generic/common/default/cust_def/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/mdm9x55/7+7_mode/dr_dsds/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/mdm9x55/7+7_mode/sr_dsds/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/mdm9x55/ss/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/mdm9x55_/7+7_mode/dr_dsds/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/mdm9x55_/7+7_mode/sr_dsds/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/mdm9x55_/ss/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/msm8998/la/7+7_mode/dr_dsds/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/msm8998/la/7+7_mode/sr_dsds/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/msm8998/la/ss/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/msm8998/wd/7+7_mode/sr_dsds/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/msm8998/wd/ss/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/msm8998/wp8/7+7_mode/dr_dsds/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/msm8998/wp8/7+7_mode/sr_dsds/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/msm8998/wp8/ss/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/generic/common/sdx20m_f/ss/mcfg_hw.mbn","image/modem_pr/mcfg/configs/mcfg_hw/oem_hw.txt","image/modem_pr/mcfg/configs/mcfg_sw/generic/china/cmcc/lab/tgl_comb/mcfg_sw.mbn","image/modem_pr/mcfg/configs/mcfg_sw/generic/eu/h3g/commerci/denmark/mcfg_sw.mbn","image/modem_pr/mcfg/configs/mcfg_sw/generic/eu/telenor/commerci/denmark/mcfg_sw.mbn","image/modem_pr/mcfg/configs/mcfg_sw/generic/latam/claro/commerci/colombia/mcfg_sw.mbn","image/modem_pr/mcfg/configs/mcfg_sw/generic/sea/smartone/commerci/hk/mcfg_sw.mbn"};
static void make_tree(const char *path){
 memset(disk,0,sizeof(disk));char component[16];unsigned dir=0,next=2;
 for(;;){const char *slash=strchr(path,'/');size_t n=slash?(size_t)(slash-path):strlen(path);assert(n<sizeof(component));memcpy(component,path,n);component[n]=0;
 entry(dir,0,component,next,slash?0:4,slash!=NULL);if(!slash){memcpy(disk+fs_cluster_off(next),"DEEP",4);break;}dir=next++;path=slash+1;}
}
int main(void){
 fs.cluster_bytes=512;fs.root_bytes=512;fs.clusters=126;fs.data_off=1024;fs.fat=fat;fs.fat_bytes=sizeof(fat);
 for(unsigned i=0;i<128;i++)fat[i]=0xffff;
 entry(0,0,"image",2,0,true);entry(2,0,"modem_pr",3,0,true);entry(3,0,"mcfg",4,0,true);entry(4,0,"configs",5,0,true);
 entry(5,0,"mcfg_hw",6,0,true);entry(6,0,"mbn_hw.dig",7,4,false);memcpy(disk+fs_cluster_off(7),"HARD",4);
 entry(5,1,"mcfg_sw",8,0,true);entry(8,0,"mbn_sw.dig",9,4,false);memcpy(disk+fs_cluster_off(9),"SOFT",4);
 entry(2,1,"wlanmdsp.mbn",10,4,false);memcpy(disk+fs_cluster_off(10),"WLAN",4);
 const char *hw="image/modem_pr/mcfg/configs/mcfg_hw/mbn_hw.dig",*sw="image/modem_pr/mcfg/configs/mcfg_sw/mbn_sw.dig";
 uint64_t size;char out[8];assert(eq_firmware_path(hw) && eq_firmware_path(sw));
 assert(!eq_firmware_size(NULL,hw,&size) && size==4);assert(!eq_firmware_read(NULL,hw,0,out,4) && !memcmp(out,"HARD",4));
 assert(!eq_firmware_read(NULL,sw,0,out,4) && !memcmp(out,"SOFT",4));
 assert(eq_firmware_read(NULL,sw,3,out,2)!=0 && eq_firmware_read(NULL,sw,UINT64_MAX,out,1)!=0);
 assert(!eq_firmware_read(NULL,"image/wlanmdsp.mbn",0,out,4) && !memcmp(out,"WLAN",4));
 const char *bad[]={"image/../x","image/modem_pr//x","image/modem_pr/./x","image/modem_pr/mcfg/","image/modem_pr/abcdefghi.dig","image/modem_pr/a.abcd","image/modem_pr/a.b.c","image/modem_pr/.a","image/modem_pr/a.","image/modem_pr/a:b","image/readwrite/mcfg.tmp","image/a/b"};
 for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++)assert(!eq_firmware_path(bad[i]));
 struct fs_file file;assert(!fs_lookup("image/modem_pr/mcfg/configs/mcfg_hw/mbn_hw.digEXTRA",&file));
 assert(!fs_lookup("image/modem_pr/../mcfg",&file));assert(!fs_lookup(NULL,&file));
 /* Invalid directory cluster cannot alias root or underflow an offset. */
 entry(2,0,"modem_pr",0,0,true);assert(!fs_lookup(hw,&file));entry(2,0,"modem_pr",200,0,true);assert(!fs_lookup(hw,&file));entry(2,0,"modem_pr",3,0,true);
 read_fail=true;assert(eq_firmware_size(NULL,hw,&size)!=0);read_fail=false;mount_ok=false;assert(eq_firmware_size(NULL,hw,&size)!=0);mount_ok=true;
 char path[263];const char *aliases[]={"/readonly/vendor/firmware_mnt/image/wlanmdsp.mbn","/readonly/vendor/firmware/wlanmdsp.mbn","/readonly/firmware/image/wlanmdsp.mbn","image/wlanmdsp.mbn"};
 for(unsigned i=0;i<4;i++){assert(file_path(aliases[i],path) && !strcmp(path,"image/wlanmdsp.mbn"));assert(!eq_firmware_size(NULL,path,&size) && size==4);}
 assert(file_path("/readonly/vendor/firmware_mnt/image/modem_pr/mcfg/configs/mcfg_hw/mbn_hw.dig",path) && !strcmp(path,hw));
 assert(!file_path("/readonly/vendor/firmware/../x",path));
 eq_firmware_mcfg_probe();assert(!allocations);
 /* Replay every deep MCFG path actually reported by the phone. */
 for(unsigned i=0;i<sizeof(observed)/sizeof(observed[0]);i++){
  assert(eq_firmware_path(observed[i]));make_tree(observed[i]);assert(!eq_firmware_size(NULL,observed[i],&size) && size==4);
  assert(!eq_firmware_read(NULL,observed[i],0,out,4) && !memcmp(out,"DEEP",4));
 }
 char depth[300]="image/modem_pr";
 for(unsigned i=0;i<22;i++)strcat(depth,"/a");assert(eq_firmware_path(depth));make_tree(depth);assert(fs_lookup(depth,&file));
 strcat(depth,"/a");assert(!eq_firmware_path(depth) && !fs_lookup(depth,&file));
 char overlong[300]="image/modem_pr";for(unsigned i=0;i<21;i++)strcat(overlong,"/abcdefgh.abc");assert(strlen(overlong)>255 && !eq_firmware_path(overlong));
 assert(fs_component83("7+7_mode",8) && !fs_component83("7+7_modes",9));
 assert(!eq_firmware_path("image/modem_pr/../7+7_mode/x"));assert(!allocations);
 /* VFAT single-slot + name, checksum binding and cross-cluster state. */
 const char *plus="image/modem_pr/7+7_mode/mcfg_hw.mbn";
 make_tree(plus);entry(3,1,"7_7_M~1",4,0,true);
 uint8_t *le=disk+fs_cluster_off(3),*se=le+32;
 memset(le,255,32);le[0]=0x41;le[11]=15;le[12]=0;le[13]=fs_name_checksum(se);le[26]=le[27]=0;
 unsigned positions[]={1,3,5,7,9,14,16,18,20,22,24,28,30};
 for(unsigned i=0;i<9;i++){le[positions[i]]=i<8?(uint8_t)"7+7_mode"[i]:0;le[positions[i]+1]=0;}
 assert(!eq_firmware_read(NULL,plus,0,out,4) && !memcmp(out,"DEEP",4));
 le[13]^=1;assert(eq_firmware_size(NULL,plus,&size)!=0);le[13]^=1;
 le[0]=0x42;assert(eq_firmware_size(NULL,plus,&size)!=0);le[0]=0x41;
 le[12]=1;assert(eq_firmware_size(NULL,plus,&size)!=0);le[12]=0;
 le[26]=1;assert(eq_firmware_size(NULL,plus,&size)!=0);le[26]=0;
 le[2]=1;assert(eq_firmware_size(NULL,plus,&size)!=0);le[2]=0;
 uint8_t saved_lfn[32],saved_short[32];memcpy(saved_lfn,le,32);memcpy(saved_short,se,32);
 memset(le,0,512);for(unsigned i=0;i<15;i++)le[i*32]=0xe5;
 memcpy(le+15*32,saved_lfn,32);memcpy(disk+fs_cluster_off(20),saved_short,32);fat[3]=20;
 assert(!eq_firmware_read(NULL,plus,0,out,4) && !memcmp(out,"DEEP",4));fat[3]=0xffff;


 puts("0161 actual deep FAT16 and every observed MCFG path passed (24-component/255-byte bounds, plus names): HW/SW content, original firmware, strict 8.3/traversal/depth, corrupt directory cluster, read/mount failure and bounds");return 0;
}
"""
 c=dev/'test.c';c.write_text(harness);exe=root/'test'
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wno-unused-function','-fsanitize=address,undefined','-I',str(dev),str(c),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
