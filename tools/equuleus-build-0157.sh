#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test "$(git branch --show-current)" = port/equuleus
sha256sum -c equuleus-0157-SHA256SUMS
python3 tools/tests/test-equuleus-rmtfs.py
python3 - <<'PYFIX'
from pathlib import Path
p=Path('shim/loader.c');s=p.read_text()
old=""" struct eq_rmt_contract contract={EQ_RMT_MAGIC,1,EQ_RMT_POOL,EQ_RMT_SPAN,EQ_RMT_DATA,EQ_RMT_BYTES,EQ_RMT_GUARD,0};
 contract.checksum=eq_rmt_checksum(&contract);
 copy64(EQ_RMT_POOL,(uintptr_t)&contract,sizeof(contract));
"""
new=""" /* Direct volatile stores avoid compiler-generated memcpy. */
 volatile struct eq_rmt_contract *contract=(volatile struct eq_rmt_contract *)EQ_RMT_POOL;
 contract->version=1;
 contract->pool=EQ_RMT_POOL;
 contract->span=EQ_RMT_SPAN;
 contract->data=EQ_RMT_DATA;
 contract->bytes=EQ_RMT_BYTES;
 contract->guard=EQ_RMT_GUARD;
 contract->checksum=EQ_RMT_MAGIC ^ 1ull ^ EQ_RMT_POOL ^ EQ_RMT_SPAN ^ EQ_RMT_DATA ^ EQ_RMT_BYTES ^ EQ_RMT_GUARD;
 __asm__ volatile("dsb sy" ::: "memory");
 contract->magic=EQ_RMT_MAGIC;
"""
if old in s:p.write_text(s.replace(old,new,1))
elif 'contract->magic=EQ_RMT_MAGIC;' not in s:raise SystemExit('Unexpected loader.c: refusing to overwrite local code')
PYFIX
# Reuse the user's verified 0156 payload for a complete shim compile/link check.
# This creates only local build output; it does not boot or flash a device.
test -s xnu/out/equuleus-rmtfs-preflight-0156.payload || {
  echo "Missing previous xnu/out/equuleus-rmtfs-preflight-0156.payload" >&2
  exit 1
}
BOARD=equuleus EQUULEUS_XNU_BOOT=1 EQUULEUS_RMTFS_RESERVE=1 \
  bash shim/build.sh ../xnu/out/equuleus-rmtfs-preflight-0156.payload
python3 - <<'PY'
from pathlib import Path
p=Path('.gitattributes');s=p.read_text() if p.exists() else ''
for name in ['xnu/patches/0157-equuleus-rmtfs-ram-service.patch']:
    line=name+' -whitespace'
    if line not in s.splitlines():s+=('' if not s or s.endswith('\n') else '\n')+line+'\n'
p.write_text(s)
PY
git add .gitattributes xnu/patches/0157-equuleus-rmtfs-ram-service.patch \
  shim/loader.c tools/equuleus-ci-verify.py \
  tools/tests/test-equuleus-rmtfs.py tools/tests/test-equuleus-glink.py \
  tools/equuleus-build-0157.sh docs/EQUULEUS_RMTFS.md
git --no-pager diff --cached --check
if ! git diff --cached --quiet; then
  git commit -m "Add bounded equuleus RMTFS service backed only by RAM snapshots"
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
