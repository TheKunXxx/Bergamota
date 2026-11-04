#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/tests/test-equios-splash.py
python3 tools/tests/test-shim-addresses.py
test -s xnu/out/equuleus-native.adt
destination=/mnt/c/Users/TheKunX-Pro/Desktop/platform-tools
test -d "$destination"
expected=$(git log -1 --format=%H -- xnu/patches/0168-equuleus-wlfw-msa-cap.patch)
run_id=$(gh run list --repo TheKunXxx/Bergamota --workflow xnu.yml --branch port/equuleus --commit "$expected" --limit 1 --json databaseId --jq '.[0].databaseId // empty')
[[ "$run_id" =~ ^[0-9]+$ ]] || { echo "No xnu workflow run for $expected yet"; exit 1; }
gh run watch "$run_id" --repo TheKunXxx/Bergamota --exit-status
actual=$(gh run view "$run_id" --repo TheKunXxx/Bergamota --json headSha,conclusion --jq '.headSha + " " + .conclusion')
test "$actual" = "$expected success" || { echo "Unexpected kernel run: $actual"; exit 1; }
out=$(mktemp -d "$PWD/xnu/out/equuleus-0168-msa-cap.XXXXXX")
gh run download "$run_id" --repo TheKunXxx/Bergamota --name xnu-kernel --dir "$out"
(cd "$out" && sha256sum -c SHA256SUMS)
python3 tools/mkpayload.py "$out/kernel.development.sweet" xnu/out/equuleus-native.adt xnu/out/equuleus-wlfw-0168-msa-cap.payload --cmdline "debug=0x14e serial=3 cpus=8 keepsyms=1 rd=ufsroot0 ufsroot=win ufsrw=1 rootrw=1 sweetlog=1 sweetfb_native=1 sweetfb_scale=0 sweetfb_noconsole=1 sweetsample=- unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1 wdt_test=no_user_checkin wdt=-1 sweettouch=5 sweettouchdelay=90 sweetkeys=1 sweetusb=0 sweetbattery=0 sweetgpu=0 sweetwlan=4 sweetwlandelay=120 sweetmss=12 eqmsa_probe=1 eqmsa_assign=1"
BOARD=equuleus EQUULEUS_XNU_BOOT=1 EQUULEUS_RMTFS_RESERVE=1 EQUULEUS_SPLASH=1 bash shim/build.sh ../xnu/out/equuleus-wlfw-0168-msa-cap.payload
cp shim/out/shim-boot.img "$destination/equuleus-wlfw-0168-msa-cap.img"
sha256sum "$destination/equuleus-wlfw-0168-msa-cap.img"
ls -lh "$destination/equuleus-wlfw-0168-msa-cap.img"
echo "Ready for temporary fastboot boot; no device partitions changed."
