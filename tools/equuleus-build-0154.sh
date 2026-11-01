#!/usr/bin/env bash
# Apply the verified package and submit one build for this exact commit.
set -euo pipefail
cd "$(dirname "$0")/.."
test "$(git branch --show-current)" = port/equuleus
sha256sum -c equuleus-0154-SHA256SUMS
python3 tools/tests/test-equuleus-servreg.py
python3 - <<'PY'
from pathlib import Path
p=Path('.gitattributes')
s=p.read_text() if p.exists() else ''
line='xnu/patches/0154-equuleus-servreg-listener.patch -whitespace'
if line not in s.splitlines():
    p.write_text(s+('' if not s or s.endswith('\n') else '\n')+line+'\n')
PY
git add .gitattributes xnu/patches/0154-equuleus-servreg-listener.patch \
  tools/equuleus-ci-verify.py tools/tests/test-equuleus-servreg.py \
  tools/tests/test-equuleus-glink.py tools/equuleus-build-0154.sh \
  docs/EQUULEUS_SERVREG.md
git --no-pager diff --cached --check
if ! git diff --cached --quiet; then
  git commit -m "Add bounded equuleus WLAN PD service notifier test"
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
  echo "Build submitted for $build_commit; it may take a moment to appear."
fi
