# HEROLTE UI probe implementation plan

> **For agentic workers:** Use superpowers:executing-plans to run and verify each step.

**Goal:** Recover an iOS screen image after an unattended test boot and exercise one synthetic Home press.

**Architecture:** An opt-in kernel probe samples the panel buffer just before the existing timed TWRP return. It writes numbered RGB565 rows to the existing persistent log. The host decodes a complete capture into PNG.

**Tech stack:** XNU HEROLTE, ADB recovery and Python 3.

- [x] Verify the host decoder with a known color pattern and a truncated capture.
- [x] Add the boot flags, reuse the physical Home key event path and emit the capture to the log.
- [x] Build the HEROLTE kernel in the private build repository.
- [x] Start from TWRP, boot with `herotwrp=120 herocap=1 herohome=1`, recover the log and inspect the PNG. Confirm actual screen content and the timed return separately.
