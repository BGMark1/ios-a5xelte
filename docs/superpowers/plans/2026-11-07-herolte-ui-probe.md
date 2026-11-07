# HEROLTE UI probe implementation plan

> **For agentic workers:** Use superpowers:executing-plans to run and verify each step.

**Goal:** Recover an iOS screen image after an unattended test boot and exercise one synthetic Home press.

**Architecture:** An opt-in kernel probe samples the panel buffer just before the existing timed TWRP return. It writes numbered RGB565 rows to the existing persistent log. The host decodes a complete capture into PNG.

**Tech stack:** XNU HEROLTE, ADB recovery and Python 3.

- [x] Verify the host decoder with a known color pattern and a truncated capture.
- [x] Add the boot flags, reuse the physical Home key event path and emit the capture to the log.
- [x] Build the HEROLTE kernel in the private build repository.
- [x] Start from TWRP, boot with `herotwrp=120 herocap=1 herohome=1`, recover the log and inspect the PNG. Confirm actual screen content and the timed return separately.

**Repeatable performance check**

- [x] Add an opt-in `heroswipe=1` sequence to the timed probe. Start from Home and alternate horizontal swipes. Mark the exact gesture window in the log.
- [x] Summarize only the framebuffer samples contained inside that window. Reject a log with no complete window.
- [x] Boot the same kernel with baseline and raised clocks, each with the same gesture sequence. Check that both screenshots show the expected UI before comparing the measured samples.
