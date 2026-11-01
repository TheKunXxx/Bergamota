#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test "$(git branch --show-current)" = port/equuleus
sha256sum -c equuleus-0156-SHA256SUMS
shim_patch=tools/patches/0156-equuleus-rmtfs-shim.patch
if git apply --reverse --check "$shim_patch" >/dev/null 2>&1; then
  echo "RMTFS shim changes already applied"
else
  git apply --check "$shim_patch"
  git apply "$shim_patch"
fi
python3 tools/tests/test-equuleus-rmtfs-preflight.py
# Compile the actual freestanding loader locally before spending a CI build.
if [ -n "${CROSS:-}" ]; then
  probe_cross=$CROSS
elif command -v aarch64-linux-gnu-gcc >/dev/null; then
  probe_cross=aarch64-linux-gnu-
else
  probe_cross=aarch64-elf-
fi
probe_tmp=$(mktemp -d)
trap 'rm -rf "$probe_tmp"' EXIT
"${probe_cross}gcc" -O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only \
  -mstrict-align -fno-stack-protector -Wall -Wextra -Werror \
  -DBOARD_EQUULEUS -DEQUULEUS_XNU_BOOT -DEQUULEUS_RMTFS_RESERVE \
  -c shim/loader.c -o "$probe_tmp/loader.o"
"${probe_cross}readelf" -r "$probe_tmp/loader.o" > "$probe_tmp/loader.relocations"
if grep -q ABS64 "$probe_tmp/loader.relocations"; then
  echo "Unexpected absolute relocation in loader" >&2
  exit 1
fi
echo "Actual AArch64 loader compile passed"
python3 - <<'PY'
from pathlib import Path
p=Path('.gitattributes');s=p.read_text() if p.exists() else ''
for name in ['xnu/patches/0156-equuleus-rmtfs-pool-preflight.patch','tools/patches/0156-equuleus-rmtfs-shim.patch']:
    line=name+' -whitespace'
    if line not in s.splitlines():s+=('' if not s or s.endswith('\n') else '\n')+line+'\n'
p.write_text(s)
PY
git add .gitattributes xnu/patches/0156-equuleus-rmtfs-pool-preflight.patch \
  shim/loader.c shim/build.sh shim/equuleus_rmtfs_contract.h shim/equuleus_rmtfs_fdt.h \
  tools/patches/0156-equuleus-rmtfs-shim.patch tools/equuleus-ci-verify.py \
  tools/tests/test-equuleus-rmtfs-preflight.py tools/equuleus-build-0156.sh \
  docs/EQUULEUS_RMTFS_PREFLIGHT.md
git --no-pager diff --cached --check
if ! git diff --cached --quiet; then
  git commit -m "Reserve and validate equuleus RMTFS pool before modem sharing"
fi
git push equuleus port/equuleus
build_commit=$(git rev-parse HEAD)
existing_run=$(gh run list --repo TheKunXxx/Bergamota --workflow 401891298 \
  --branch port/equuleus --commit "$build_commit" --limit 1 \
  --json databaseId --jq '.[0].databaseId // empty')
if [ -n "$existing_run" ]; then
  echo "Build already exists for this commit: $existing_run"
  gh run view "$existing_run" --repo TheKunXxx/Bergamota
else
  gh workflow run 401891298 --repo TheKunXxx/Bergamota --ref port/equuleus \
    -f macos_version=13.5 -f kernel_config=DEVELOPMENT \
    -f machine_config=SWEET -f keep_going=true
  echo "Build submitted for $build_commit"
fi
