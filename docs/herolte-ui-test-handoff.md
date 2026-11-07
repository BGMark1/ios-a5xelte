# HEROLTE UI test handoff

The test device is a Galaxy S7 SM-G930F running the HEROLTE port. The current control image presents a 1242 × 2208 iOS canvas, enables the audio driver, and requests 1976 MHz on the Mongoose cores and 546 MHz on the Mali GPU. The recovered boot log confirms both clock settings. SpringBoard logged the icon width change from 56 to 60.48 points. The captures confirm that the red diagnostic status bar still appears on the home screen.

The SpringBoard wrapper source is `tools/ios/herolte-home-ui.c`. The compiled wrapper in the workspace is `s7-setup/libhomeui-test.dylib`. The drop package installs it as `lib/libherosb.dylib` and keeps the original wallpaper library as `lib/libherosb-base.dylib`. It also carries the audio installer and original Samsung wifi firmware and NVRAM. The timed screenshot test reuses that package. The control boot and drop package together are the rollback baseline for this round.

The test patch `xnu/patches/0322-herolte-panel-capture.patch` samples the actual BGRA panel buffer as 480 × 853 RGB565. With `herotwrp=120 herocap=1 herohome=1`, the existing recovery thread sends one Home press, captures the panel four seconds later, and returns to TWRP after allowing the existing log flush to run. Capture and input are opt-in test flags. A Home event can wake a locked phone. The result may therefore be the lock screen.

The [private XNU build](https://github.com/BGMark1/galaxy-s7-ios-private-build/actions/runs/42327839616) uses branch `codex/herolte-ui-probe` and commit `770aa382999cb2ad377713334a559094eab61297`. Download the `xnu-kernel-macos-15-intel` artifact and check `SHA256SUMS`. Pack the resulting `kernel.development.herolte` with the current 8 Plus ADT and the control image's boot arguments plus the three test flags. The control image in the local workspace is `s7-setup/audio-ui-clock-test.img`, SHA-256 `48b48be84cd3ff26f70bbcf5bbd54189de956a1bb670f9aad30ade8258319a68`.

With the S7 in TWRP, run:

```text
python tools/herolte-ui-test.py ADB SERIAL TEST.img CONTROL.img NEW_OUTPUT_DIRECTORY
```

The runner checks the model, recovery, BOOT partition and control image hash. It verifies the written test image, waits for a new recovery session, extracts a fresh log and decodes the PNG. It then restores and verifies the control BOOT and leaves the phone in recovery. If recovery never returns, the hardware buttons are required to enter TWRP before restoring the control BOOT. The runner writes only BOOT from TWRP. The kernel sends capture data through the already installed persistent log.

The host decoder has been checked with known RGB565 colors, a full-size synthetic capture and a truncated capture. A successful device trial requires an actual image, a new boot log containing the Home marker, and a verified return to TWRP. Keep screenshots and device logs out of the repository. Future tap and swipe tests can reuse the touch driver event path once the first timed Home and capture trial is verified.

The first device run produced a complete PNG showing the home screen, including the red diagnostic bar. XNU logged the Home key down and up with one HID client and reached the timed recovery path. ADB detected TWRP shortly after the original host timeout, so the runner now allows 150 seconds beyond the in-kernel timer. The SpringBoard diagnostic scan had also ended before the Home key event. The next run extends it to 90 checks at two-second intervals.

The second run completed end to end. The runner booted the probe, observed the return to TWRP, extracted a fresh PNG and restored the verified control BOOT. The updated diagnostic scan still did not hide the red bar in the captured home screen. Inspect which process owns the diagnostic view before changing status bar behavior again. The test kernel SHA-256 is `82bd87d8c531aea421c90257c542e48b26546572430411af4c37e053ceb24d2f`. The local test artifacts are under `s7-setup/xnu-ui-probe-42327839616/device-test-2`.

The control boot peaked at 59.3 displayed frames/s over a five-second log interval. Its median reported frame copy time was 4.37 ms. The first unattended boot's median was 4.30 ms, with different screen activity. A matched swipe test is still needed to compare UI smoothness.

The control log reports eight initialized CPUs and verified interprocessor interrupts. Patch `0238` already prefers the four Mongoose cores for high-priority work through the default mask `0xf0`. The Snapdragon S9 port is a reference for a second, independent experiment. Its CoreAnimation measurements improved when libdispatch reported a parallelism of two for the relevant QoS classes. Compare reproducible scroll tests and interprocessor interrupt rates on the S7 before choosing a default. The S9 also demonstrates an SSH-based workflow, which can inform live control on the S7 after the offline capture test. Its USB controller and panel code are hardware-specific. [S9 measurement notes](https://github.com/syncmodz/ios-s9/blob/main/s9/NOTES.md)
