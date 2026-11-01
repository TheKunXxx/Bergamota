#!/usr/bin/env python3
"""Link actual AArch64 entry with >3MiB rodata and verify runtime address deltas."""
from pathlib import Path
import os,re,shutil,struct,subprocess,tempfile
repo=Path(__file__).resolve().parents[2]
prefix=os.environ.get('CROSS','')
if not prefix:
 prefix=next((p for p in ('aarch64-linux-gnu-','aarch64-elf-') if shutil.which(p+'as')),None)
if not prefix:raise SystemExit('AArch64 binutils required for shim address regression test')
with tempfile.TemporaryDirectory() as td:
 root=Path(td);fixture=root/'fixture.S';fixture.write_text('.section .rodata\n.space 0x300000,0\n.bss\n.space 256\n.text\n.globl shim_main,secondary_main,exc_handler\nshim_main: ret\nsecondary_main: ret\nexc_handler: ret\n')
 subprocess.run([prefix+'as','-L',str(repo/'shim/start.S'),'-o',str(root/'start.o')],check=True)
 subprocess.run([prefix+'as',str(fixture),'-o',str(root/'fixture.o')],check=True)
 subprocess.run([prefix+'ld','-T',str(repo/'shim/shim.ld'),'-o',str(root/'test.elf'),str(root/'start.o'),str(root/'fixture.o')],check=True,capture_output=True)
 subprocess.run([prefix+'objcopy','-O','binary',str(root/'test.elf'),str(root/'test.bin')],check=True)
 lines=subprocess.run([prefix+'nm','-a',str(root/'test.elf')],check=True,capture_output=True,text=True).stdout.splitlines()
 symbols={parts[2]:int(parts[0],16) for line in lines if len(parts:=line.split())==3 and re.fullmatch('[0-9a-fA-F]+',parts[0])}
 image=(root/'test.bin').read_bytes();targets=['_stack_top','vectors','_bss_start','_bss_end','_sec_stacks','vectors']
 assert symbols['_stack_top']>0x300000 and struct.unpack_from('<Q',image,16)[0]==symbols['_end']
 for i,target in enumerate(targets):
  location=symbols[f'.Laddr{i}'];delta=struct.unpack_from('<q',image,location)[0]
  for base in (0,0x8000,0x81234567,0x100000000):assert base+location+delta==base+symbols[target]
 reloc=subprocess.run([prefix+'readelf','-rW',str(root/'start.o')],check=True,capture_output=True,text=True).stdout
 assert reloc.count('R_AARCH64_ABS64')==1 and '_end' in reloc
 for line in reloc.splitlines():
  if 'R_AARCH64_ADR_PREL_LO21' in line:assert not any(name in line for name in targets)
print('Actual AArch64 entry linked with3MiB rodata; six relative addresses verified at four load bases; only Image header has ABS64')
