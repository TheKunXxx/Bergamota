#!/usr/bin/env python3
"""Replay 0175 with fake MMIO; no hardware/ASM claims are made by this test."""
import os
from pathlib import Path
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[2]
patch = repo / 'xnu/patches/0175-equuleus-wlfw-msa-translate.patch'
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    subprocess.run(['git', 'apply', '--include=bsd/dev/equuleus_wlfw_smmu.h',
                    str(patch)], cwd=root, check=True)
    subprocess.run(['git', 'apply', str(repo / 'xnu/patches/0176-equuleus-wlfw-sctlr-hint.patch')], cwd=root, check=True)
    source = (root / 'bsd/dev/equuleus_wlfw_smmu.h').read_text()
    source = source.replace('#include <vm/vm_kern.h>', '')
    source = source.replace('__asm__ volatile("dsb sy" ::: "memory");', '')
    source = source.replace('__asm__ volatile("dc civac, %0" :: "r"(va) : "memory");',
                            '(void)va;')
    (root / 'smmu175host.h').write_text(source)
    binary = root / 'test'
    subprocess.run([os.environ.get('CC', 'cc'), '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I', str(root),
                    str(repo / 'tools/tests/equuleus-smmu-0175.c'),
                    '-o', str(binary)], check=True)
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
    subprocess.run([str(binary)], env=env, check=True)
