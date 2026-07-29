"""Install/enable Apple MCC capture LaunchAgent (operator-gated)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

LABEL = "com.local.apple-mcc.capture"


def install(*, enable: bool = True, interval_seconds: int = 3600, working_directory: Path | None = None) -> dict:
    py = sys.executable
    cwd = Path(working_directory or Path.cwd()).resolve()
    src = cwd / "src"
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / f"{LABEL}.plist"
    logs = (
        Path.home()
        / "Library"
        / "Application Support"
        / "HB Personal Assistant"
        / "logs"
        / "apple-mcc"
    )
    logs.mkdir(parents=True, exist_ok=True)
    out_log = logs / "capture.out.log"
    err_log = logs / "capture.err.log"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
        '<plist version="1.0">',
        "<dict>",
        "  <key>Label</key>",
        f"  <string>{LABEL}</string>",
        "  <key>ProgramArguments</key>",
        "  <array>",
        f"    <string>{py}</string>",
        "    <string>-m</string>",
        "    <string>hb_assistant.cli.apple_mcc</string>",
        "    <string>capture</string>",
        "    <string>--domains</string>",
        "    <string>mail,calendar,contacts</string>",
        "    <string>--mail-limit</string>",
        "    <string>10</string>",
        "    <string>--calendar-limit</string>",
        "    <string>50</string>",
        "    <string>--contacts-limit</string>",
        "    <string>25</string>",
        "    <string>--contacts-containers</string>",
        "    <string>iCloud,BF-Personal</string>",
        "    <string>--calendar-sources</string>",
        "    <string>iCloud</string>",
        "  </array>",
        "  <key>WorkingDirectory</key>",
        f"  <string>{cwd}</string>",
        "  <key>EnvironmentVariables</key>",
        "  <dict>",
        "    <key>PYTHONPATH</key>",
        f"    <string>{src}</string>",
        "    <key>APPLE_MCC_LIVE</key>",
        "    <string>1</string>",
        "  </dict>",
        "  <key>RunAtLoad</key>",
        "  <true/>",
        "  <key>StartInterval</key>",
        f"  <integer>{int(interval_seconds)}</integer>",
        "  <key>StandardOutPath</key>",
        f"  <string>{out_log}</string>",
        "  <key>StandardErrorPath</key>",
        f"  <string>{err_log}</string>",
        "</dict>",
        "</plist>",
        "",
    ]
    plist_path.write_text("\n".join(lines), encoding="utf-8")

    uid = os.getuid()
    domain = f"gui/{uid}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)
    result = {
        "label": LABEL,
        "plist": str(plist_path),
        "enabled": False,
        "working_directory": str(cwd),
    }
    if not enable:
        return result

    proc = subprocess.run(
        ["launchctl", "bootstrap", domain, str(plist_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        proc = subprocess.run(
            ["launchctl", "load", "-w", str(plist_path)],
            capture_output=True,
            text=True,
        )
    kick = subprocess.run(
        ["launchctl", "kickstart", "-k", f"{domain}/{LABEL}"],
        capture_output=True,
        text=True,
    )
    result.update(
        {
            "enabled": True,
            "bootstrap_rc": proc.returncode,
            "bootstrap_err": (proc.stderr or "")[:500],
            "kickstart_rc": kick.returncode,
            "kickstart_err": (kick.stderr or "")[:500],
        }
    )
    return result


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--disable", action="store_true")
    p.add_argument("--interval", type=int, default=3600)
    p.add_argument("--cwd", type=Path, default=None)
    args = p.parse_args()
    print(
        json.dumps(
            install(enable=not args.disable, interval_seconds=args.interval, working_directory=args.cwd),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
