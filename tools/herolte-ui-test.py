#!/usr/bin/env python3
"""Run a timed HEROLTE screen test from TWRP and recover its log and PNG."""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path


BOOT = "/dev/block/sda5"
BOOT_LINK = "/dev/block/platform/155a0000.ufs/by-name/BOOT"
BOOT_SIZE = 40 * 1024 * 1024
REMOTE_IMAGE = "/tmp/herolte-ui-test.img"
TOOLS = Path(__file__).resolve().parent


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def shell(adb, command):
    return subprocess.check_output(adb + ["shell", command], text=True).strip()


def is_recovery(adb):
    state = subprocess.run(adb + ["get-state"], capture_output=True, text=True, timeout=5)
    return state.returncode == 0 and state.stdout.strip() == "recovery"


def check_recovery(adb):
    if not is_recovery(adb):
        raise RuntimeError("device is not connected in TWRP")
    values = shell(adb, f"getprop ro.product.device; getprop ro.twrp.version; "
                        f"readlink -f {BOOT_LINK}; blockdev --getsize64 {BOOT}").splitlines()
    if len(values) != 4 or values[0] != "herolte" or not values[1] or values[2:] != [BOOT, str(BOOT_SIZE)]:
        raise RuntimeError("unexpected recovery device or BOOT partition")


def boot_hash(adb, size):
    return shell(adb, f"head -c {size} {BOOT} | sha256sum").split()[0]


def flash(adb, image, data):
    check_recovery(adb)
    expected = sha256(data)
    subprocess.run(adb + ["push", str(image), REMOTE_IMAGE], check=True)
    if shell(adb, f"sha256sum {REMOTE_IMAGE}").split()[0] != expected:
        raise RuntimeError("BOOT upload hash mismatch")
    shell(adb, f"dd if={REMOTE_IMAGE} of={BOOT} bs=1048576 && sync")
    if boot_hash(adb, len(data)) != expected:
        raise RuntimeError("BOOT readback hash mismatch")
    print(f"Verified BOOT {expected}", flush=True)


def image_bytes(path):
    data = path.read_bytes()
    if data[:8] != b"ANDROID!" or not 0 < len(data) <= BOOT_SIZE:
        raise ValueError(f"invalid HEROLTE BOOT image: {path}")
    return data


def recovery_timeout(data):
    args = re.findall(rb"SWEETXNU.{64}(debug=[ -~]{1,606})\x00", data, re.S)
    if len(args) != 1:
        raise ValueError("expected one HEROLTE XNU payload")
    flags = args[0].split()
    timers = [flag for flag in flags if flag.startswith(b"herotwrp=")]
    if b"herocap=1" not in flags or len(timers) != 1:
        raise ValueError("image must request both timed recovery and a screen capture")
    seconds = int(timers[0].split(b"=", 1)[1])
    if not 30 <= seconds <= 300:
        raise ValueError("herotwrp must be between 30 and 300 seconds")
    # The timer starts inside XNU. Allow for bootloader time, capture and USB enumeration.
    return seconds + 150


def wait_for_return(adb, timeout):
    deadline = time.monotonic() + timeout
    departed = False
    while time.monotonic() < deadline:
        try:
            recovery = is_recovery(adb)
        except subprocess.TimeoutExpired:
            recovery = False
        if not recovery:
            departed = True
        elif departed:
            check_recovery(adb)
            return
        time.sleep(2)
    raise RuntimeError("timed return was not observed; bring the phone back to TWRP manually")


def pull_log(adb_path, serial, output):
    env = dict(os.environ, ANDROID_SERIAL=serial)
    subprocess.run([sys.executable, str(TOOLS / "herolte-log-pull.py"), adb_path, str(output)],
                   check=True, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adb", type=Path)
    parser.add_argument("serial")
    parser.add_argument("test", type=Path)
    parser.add_argument("restore", type=Path, help="image that must currently be in BOOT")
    parser.add_argument("output", type=Path, help="new output directory")
    args = parser.parse_args()
    adb_path = str(args.adb.resolve())
    adb = [adb_path, "-s", args.serial]
    try:
        test = image_bytes(args.test)
        restore = image_bytes(args.restore)
        timeout = recovery_timeout(test)
        check_recovery(adb)
        if boot_hash(adb, len(restore)) != sha256(restore):
            raise RuntimeError("restore image does not match the current BOOT")
        args.output.mkdir(parents=True)
        before = args.output / "before.txt"
        after = args.output / "test.txt"
        pull_log(adb_path, args.serial, before)
        flash(adb, args.test, test)
        subprocess.run(adb + ["reboot"], check=True)
        wait_for_return(adb, timeout)
        try:
            pull_log(adb_path, args.serial, after)
            if sha256(before.read_bytes()) == sha256(after.read_bytes()):
                raise RuntimeError("recovery returned the previous boot log")
            subprocess.run([sys.executable, str(TOOLS / "herolte-screen.py"), str(after),
                            str(args.output / "screen.png")], check=True)
        finally:
            flash(adb, args.restore, restore)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
