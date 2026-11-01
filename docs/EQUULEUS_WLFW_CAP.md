# Equuleus 0163: correct WLFW service and capability-only query

Correction to earlier analysis: WLFW is QRTR service **69 decimal (0x45)**, version1, instance0. The previous summaries incorrectly searched for decimal45. Service69 was already present in the real-device logs. The pinned dipper-xnu commit4e82c709ea42ebb509fa101b52972fdc890b873e uses lookup69 and QMI CAP message0x24 with an empty payload. Source references: patches/xnu-mi8.patch, mi8_wlfw.c and mi8_wlfw_qmi.h sections. Earlier claims that WLFW had not appeared were wrong; no further waiting for its discovery is justified.

Mode12 now opens a diagnostic QRTR port, looks up69/v1/instance0 and, after the existing WLAN PD UP notification, sends CAP. The request is diagnostic only: it does not register indications, enable WLAN mode, configure DMA, download board files or change MSA/SCM ownership. CAP success means the service answered a capability query, not Wi-Fi connectivity or FW_READY. A QMI failure such as INCOMPATIBLE_STATE is recorded for planning the correct initialization handshake.

The client accepts only the selected node0 peer, matching transaction/message, response type and bounded512-byte frames. All TLVs must fit, duplicate TLVs are rejected, and mandatory result TLV2 must be exactly4bytes with a consistent result/error pair. Unknown bounded TLVs are counted but not interpreted or logged as strings. Retries are limited to3 attempts separated by2seconds; reentrant responses are supported. Server removal clears pending/success state, and the port closes before the transport is destroyed. The180-second outer budget, RAM-only RMTFS, host services and no-reclaim guard are unchanged.

Expected lines: `eqwl: capability probe start=1 service=69/0x45`, selected peer, CAP request and `CAP response result=... qmi_error=...`, then a summary. Missing/timeout/failure is evidence to inspect, never converted into a successful hardware initialization.

Tests replay the complete patch chain and exercise actual client lookup/gates/reentrant responses, success/QMI error, malformed peer/transaction/frame/TLV/truncations,2000 mutated messages, bounded retry timing, server removal and close. The existing actual GLINK adapter suite compiles the integration. Full XNU build and a phone test remain required.

## EquiOS loader splash

The approved final artwork with EquiOS and ChatGPT knot is included as `shim/assets/equios-splash.rle`. Source PNG SHA256:339714a857a6571ee3602663768b2894f459e81b781f0432470ccc35b8919631. It was proportionally fitted to1080x2248, using a256-color palette and lossless run encoding of those palette indices. Visible bounds are x88..999,y290..2075, leaving at least80px at the sides,290px above and172px below for physical notch/corners. It is the user's selected image, not a new generation.

The equuleus XNU loader renders it, waits3000ms after drawing and resumes boot. The branch's console background is black. `EQUULEUS_SPLASH=0` disables the image; other boards do not display it. The renderer validates magic/dimensions/palette/runs and total pixels before framebuffer writes. Native stride handling does not write row padding. The embedded object is included in the existing absolute-relocation check. Existing RMTFS reservation and volatile contract-store fix are preserved.

Native tests verify the actual embedded renderer, asset checksum, safe visible bounds, frame canaries and malformed-stream refusal. They do not replace an AArch64 link or device display test. The build helper compiles the new shim using the existing0162 payload if it is present, before submitting XNU CI. This compiles locally but does not flash or boot the phone or copy a new Windows image. After CI succeeds, build the new payload/image using the new kernel as usual.

## Large-image entry fix

The splash made the shim larger than the roughly1MiB reach of AArch64 ADR. The initial stack/BSS/secondary-stack address instructions therefore failed at link time. start.S now obtains those addresses (and vectors) from nearby literals storing signed link-time target-minus-literal deltas. The local ADR reaches only the nearby literal; adding the loaded delta computes the runtime address without embedding an absolute pointer. x9 is scratch; x0/x19 boot arguments remain intact. Existing aligned Android Image loading requirements still apply.

The new test assembles the actual start.S with GNU AArch64 tools, links it with3MiB of rodata using the actual shim linker script, checks all six address deltas at four hypothetical load bases, verifies image_size and verifies that only the existing Image-header _end field uses ABS64. This validates linking and address arithmetic, not ARM CPU execution. The normal helper runs this test and then the full shim build before XNU dispatch when the previous payload is present.
