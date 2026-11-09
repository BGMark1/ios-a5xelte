# Galaxy S7 (SM-G930F, herolte) kernel patches

These are BGMark1's kernel patches for the Samsung Galaxy S7 (SM-G930F, Exynos 8890). They were developed outside this repository and are contributed here as a reference series and build toolset. They are not part of the upstream history.

## Base

- Base: build tree of private CI run 42477676441.
- Source revision: e929651.
- XNU version: 8796.141.3, DEVELOPMENT, HEROLTE configuration.

## Layout

- `patches/combined/perf16-combined.patch`: the full diff against the base above. It is authoritative for the complete state of the work. It includes:
  - RAM banks (3058 MB) and the WIMG fix (0334).
  - Frame timing and GPU sleep-wait.
  - MAX77854 charger page (0x69), MUIC charger type, and the input limit `herochgin`.
  - Fuel-gauge SOC, temperature and cycle count.
  - Haptic PWM and the iOS `vibrator` IOService. Vibration from iOS has been confirmed by the user.
  - CPU load log.
  - vmd CPU cap `herovmdcap` (default 5%). The user noticed less heat.
  - IOMFBBrightnessLevel setProperties (0348).
  - Optional `herobacklight=1` SweetBacklight service (0349). Brightness from iOS is NOT working yet.
- `patches/series/`: the individual steps, numbered in the local development sequence. Those numbers collide with upstream patch numbers 0320–0331, so renumber before integrating into any upstream tree.
- `local-build/`: the scripts used to build the kernels locally (build.sh, check-kernel.py, compat-replay.py, replay-link.py, replay-objects.py) with a README and SHA256SUMS. No binaries or kernel images are included.

## Status and evidence

- Per-patch status claims (built, booted, user-observed) are recorded in `HEROLTE_PROGRESS.md` at the repository root. That file is written in Spanish.
- The kernels were built locally with `local-build/`. All of them were scanned and contain 0 LSE instructions.
- The daily kernel in use is perf14, which includes patches up to 0347.
