#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test "$(git branch --show-current)" = port/equuleus
python3 tools/tests/test-equuleus-firmware-paths.py
EQUULEUS_TEST_0160=1 python3 tools/tests/test-equuleus-glink.py
commit_sha=$(git rev-parse HEAD)
existing=$(gh run list --repo TheKunXxx/Bergamota --branch port/equuleus --commit "$commit_sha" --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId // empty')
if [ -n "$existing" ]; then
    echo "Existing run for $commit_sha: $existing"
else
    gh workflow run 401891298 --repo TheKunXxx/Bergamota --ref port/equuleus \
        -f macos_version=13.5 -f kernel_config=DEVELOPMENT -f machine_config=SWEET -f keep_going=true
    echo "Build submitted for $commit_sha"
fi
