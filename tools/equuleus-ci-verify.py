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
        new = '*/0148-*|*/0149-*|*/0150-*|*/0151-*|*/0152-*|*/0153-*|*/0154-*)'
        if new in text:
            return
        for old in ('*/0148-*|*/0149-*|*/0150-*|*/0151-*|*/0152-*|*/0153-*)',
                    '*/0148-*|*/0149-*|*/0150-*|*/0151-*|*/0152-*)',
                    '*/0148-*|*/0149-*|*/0150-*|*/0151-*)',
                    '*/0148-*|*/0149-*|*/0150-*)'):
            if text.count(old) == 1:
                path.write_text(text.replace(old, new))
                return
        raise SystemExit('Unknown existing required-patch guard')
    needle = '                warning "Skipping patch ${PATCH} (already upstream, previously applied, or malformed): ${APPLY_CHECK}"'
    if text.count(needle) != 1:
        raise SystemExit('Unknown build.sh patch loop; refusing to continue')
    guard = '''                # EQUULEUS_REQUIRED_PATCHES
                case "$PATCH" in
                    */0148-*|*/0149-*|*/0150-*|*/0151-*|*/0152-*|*/0153-*|*/0154-*)
                        printf '%s\\n' "Required equuleus patch failed: $PATCH" "$APPLY_CHECK" >&2
                        exit 1
                        ;;
                esac
'''
    path.write_text(text.replace(needle, guard + needle))
    print('0148/0149/0150/0151/0152/0153/0154 patch failures are now fatal')


def verify(root):
    dev = root / 'xnu/bsd/dev'
    checks = {
        dev / 'beryllium_wlan.c': [
            'uint32_t e = top + 32 + i * 48;',
            'equuleus_mss_probe();',
        ],
        dev / 'sweet_rpmh.c': ['sweet_rpmh_bus_acquire(void)',
                                'sweet_rpmh_bus_release(void)'],
        dev / 'equuleus_mss.c': ['eqmss: port 0154', 'mss_servreg_test = mode == 9;', 'equuleus_glink_probe();', 'mss_halt_all = mode == 7;', 'equuleus_mss_stop_snapshot(', 'held idle %#x', 'mss_run_mba(void)', 'equuleus_mpss_load('],
        dev / 'equuleus_servreg.c': ['equuleus_servreg_start(', 'equuleus_servreg_poll(', 'msm/modem/wlan_pd'],
        dev / 'equuleus_glink.c': ['mi8_glink_start(', 'mi8_glink_qrtr_servers('],
        root / 'xnu/bsd/conf/files': ['bsd/dev/equuleus_mss.c', 'bsd/dev/equuleus_glink.c', 'bsd/dev/equuleus_servreg.c'],
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
    for required in ('_equuleus_mss_probe', '_equuleus_mpss_load', '_equuleus_mss_stop_snapshot', '_equuleus_mss_halt_all', '_equuleus_glink_probe', '_mi8_glink_start', '_equuleus_servreg_start', '_equuleus_servreg_poll'):
        if not any(line.split()[-1:] == [required] for line in symbols.splitlines()):
            raise SystemExit(f'Missing linked kernel entry point: {required}')
    print('Required source changes and linked MSS entry point verified')
    print(hashlib.sha256(kernel.read_bytes()).hexdigest(), kernel)


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('prepare', 'verify'):
        raise SystemExit('usage: equuleus-ci-verify.py prepare BUILD.SH | verify DXB_ROOT')
    {'prepare': prepare, 'verify': verify}[sys.argv[1]](Path(sys.argv[2]))
