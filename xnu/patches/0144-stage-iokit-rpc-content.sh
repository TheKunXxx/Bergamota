#!/bin/bash
# dxb runs patches/*.sh from the XNU source root before applying *.patch.
# 0143 patches DriverKit/IORPC.h; the kernel also exports IOKit/IORPC.h.
set -euo pipefail

[[ "${MACHINE_CONFIG:-}" == SWEET ]] || exit 0
[[ "${MACOS_VERSION:-}" == 13.5 ]] || {
    echo 'IORPC compatibility requires xnu-8796.141.3 (macOS 13.5)' >&2
    exit 1
}

python3 - <<'PY'
from pathlib import Path
import re

p = Path('iokit/IOKit/IORPC.h')
s = p.read_text()
blocks = list(re.finditer(r'\bstruct\s+IORPC\s*\{(?P<body>[^{}]*)\};', s))
if len(blocks) != 1:
    raise SystemExit(f'{p}: expected exactly one IORPC definition')
m = blocks[0]
body = m.group('body')
fields = r'''
    \s*IORPCMessageMach\s*\*\s*message\s*;
    \s*IORPCMessageMach\s*\*\s*reply\s*;
    \s*uint32_t\s+sendSize\s*;
    \s*uint32_t\s+replySize\s*;
'''
addition = '''#ifdef KERNEL
	/* Match the kernel-only field added to DriverKit/IORPC.h by 0143. */
	IORPCMessage *     kernelContent;
#endif
'''
# Accept only our exact previous edit when rerun, never an unknown layout.
original = body.replace(addition, '')
if re.fullmatch(fields + r'\s*', original, re.VERBOSE) is None:
    raise SystemExit(f'{p}: unexpected IORPC layout; refusing to edit')
if body.count(addition) == 1:
    print(f'{p}: kernelContent already staged')
else:
    updated = body.rstrip() + '\n' + addition
    p.write_text(s[:m.start('body')] + updated + s[m.end('body'):])
    print(f'{p}: staged KERNEL-only kernelContent for Xcode 16 iig')
PY
