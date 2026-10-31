#!/usr/bin/env python3
"""Make equuleus patches mandatory; verify their source and linked symbol."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys


def prepare(path):
    text = path.read_text()
    marker = '# EQUULEUS_REQUIRED_PATCHES'
    if marker in text:
        return
    needle = '                warning "Skipping patch ${PATCH} (already upstream, previously applied, or malformed): ${APPLY_CHECK}"'
    if text.count(needle) != 1:
        raise SystemExit('Unknown build.sh patch loop; refusing to continue')
    guard = '''                # EQUULEUS_REQUIRED_PATCHES
                case "$PATCH" in
                    */0148-*|*/0149-*)
                        printf '%s\\n' "Required equuleus patch failed: $PATCH" "$APPLY_CHECK" >&2
                        exit 1
                        ;;
                esac
'''
    path.write_text(text.replace(needle, guard + needle))
    print('0148/0149 patch failures are now fatal')


def verify(root):
    dev = root / 'xnu/bsd/dev'
    checks = {
        dev / 'beryllium_wlan.c': [
            'uint32_t e = top + 32 + i * 48;',
            'equuleus_mss_probe();',
        ],
        dev / 'sweet_rpmh.c': ['sweet_rpmh_bus_acquire(void)',
                                'sweet_rpmh_bus_release(void)'],
        dev / 'equuleus_mss.c': ['eqmss: port 0149', 'mss_run_mba(void)'],
        root / 'xnu/bsd/conf/files': ['bsd/dev/equuleus_mss.c'],
    }
    for path, needles in checks.items():
        text = path.read_text()
        for needle in needles:
            if needle not in text:
                raise SystemExit(f'Missing required source change: {path}: {needle}')
    variant = os.environ.get('KERNEL_CONFIG', 'DEVELOPMENT').lower()
    machine = os.environ.get('MACHINE_CONFIG', 'SWEET').lower()
    kernel = root / f'fakeroot/System/Library/Kernels/kernel.{variant}.{machine}'
    symbols = subprocess.run(['nm', str(kernel)], check=True,
                             capture_output=True, text=True).stdout
    if not any(line.split()[-1:] == ['_equuleus_mss_probe']
               for line in symbols.splitlines()):
        raise SystemExit('MSS entry point is absent from the linked kernel')
    print('Required source changes and linked MSS entry point verified')
    print(hashlib.sha256(kernel.read_bytes()).hexdigest(), kernel)


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('prepare', 'verify'):
        raise SystemExit('usage: equuleus-ci-verify.py prepare BUILD.SH | verify DXB_ROOT')
    {'prepare': prepare, 'verify': verify}[sys.argv[1]](Path(sys.argv[2]))
