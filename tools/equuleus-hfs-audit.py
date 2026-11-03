#!/usr/bin/env python3
"""Read-only Android/root audit of equuleus win HFS volume headers.

No mount, filesystem repair, partition writes or device reboot is performed.
Header checks are not a full filesystem consistency check.
"""
import argparse
import json
import shutil
import struct
import subprocess

DEVICE = '/dev/block/bootdevice/by-name/win'
LOG_START = 14338559 * 4096
LOG_SIZE = 1025 * 4096


def header(data):
    if len(data) != 512 or data[:2] not in (b'H+', b'HX'):
        raise ValueError('Expected a complete HFS+/HFSX volume header')
    u32 = lambda off: struct.unpack_from('>I', data, off)[0]
    block, total = u32(40), u32(44)
    if block < 512 or block > 1048576 or block & (block - 1) or total < 4:
        raise ValueError('Invalid allocation block size/count')
    return dict(signature=data[:2].decode(), version=struct.unpack_from('>H', data, 2)[0],
                attributes=hex(u32(4)), journal_info_block=u32(12),
                block_size=block, total_blocks=total, free_blocks=u32(48),
                write_count=u32(68), volume_bytes=block * total,
                clean_unmount=bool(u32(4) & 0x100),
                inconsistent=bool(u32(4) & 0x800), journaled=bool(u32(4) & 0x2000))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', help='ADB executable (Windows adb.exe works from WSL)')
    args = parser.parse_args()
    adb = args.adb or shutil.which('adb') or shutil.which('adb.exe')
    if not adb:
        raise SystemExit('ADB not found; pass --adb /mnt/c/.../platform-tools/adb.exe')

    def remote(command):
        result = subprocess.run([adb, 'exec-out', 'su', '-c', command],
                                capture_output=True, timeout=60, check=True)
        return result.stdout

    identity = remote('getprop ro.product.device').decode().strip()
    if identity != 'equuleus':
        raise ValueError('Refusing unexpected device: ' + repr(identity))
    size = int(remote('blockdev --getsize64 ' + DEVICE).strip())
    report = dict(device=identity, partition=DEVICE, partition_bytes=size,
                  scope='Header and bounds audit only; no writes or repairs')

    def read(offset, count):
        if offset % 512 or count % 512 or offset < 0 or offset + count > size:
            raise ValueError('Read outside partition or unaligned')
        data = remote(f'dd if={DEVICE} bs=512 skip={offset // 512} count={count // 512} 2>/dev/null')
        if len(data) != count:
            raise ValueError(f'Short read at {offset}: {len(data)} of {count}')
        return data

    primary = header(read(1024, 512))
    report['primary'] = primary
    volume = primary['volume_bytes']
    if volume > size or volume < 4096:
        raise ValueError('HFS volume exceeds partition bounds')
    report['log_range_fits_partition'] = LOG_START + LOG_SIZE <= size
    report['volume_overlaps_log'] = volume > LOG_START
    report['alternate_offset'] = volume - 1024
    try:
        alternate = header(read(volume - 1024, 512))
        report['alternate'] = alternate
        report['geometry_matches'] = all(primary[k] == alternate[k] for k in
                                         ('signature', 'block_size', 'total_blocks'))
    except ValueError as error:
        report['alternate_error'] = str(error)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
