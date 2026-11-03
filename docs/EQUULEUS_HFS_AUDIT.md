# Equuleus 0164: HFS audit handoff

Hardware log: WLFW REGISTER succeeds with result=0/error=0, status_valid=1, fw_status=0; FW_READY remains false, indications=0 and CAP is not sent. This does not establish Wi-Fi connectivity or prove the sole cause of missing readiness. MSA setup remains unimplemented.

The same log repeatedly reports HFS free-unallocated-block errors and runtime inconsistency on iOSRoot. Cause is not yet established. Avoid further writable XNU boots until the root volume is examined.

Run tools/equuleus-hfs-audit.py from WSL with the phone in rooted Android, passing --adb if required. Commit 39f89f2 introduces the audit. It reads identity, partition size and primary/alternate HFS headers, checking geometry and persistent-log overlap. It performs no partition writes, repairs, mounts or reboots. Header validation is not a full filesystem consistency check.

Validation: Python compilation and a mocked end-to-end ADB test passed, including header offsets, geometry/log bounds, malformed headers and read-only command checks. Real device audit is pending. Collect JSON output before choosing backup/offline repair steps. No repair has been performed.

Before implementing MSA sharing, verify the protocol sequence, reserved-memory bounds and ownership for equuleus; do not borrow another device's memory address.
