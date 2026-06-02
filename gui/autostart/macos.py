"""macOS 开机自启后端：~/Library/LaunchAgents/*.plist + launchctl。"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

LABEL = "com.voiceinput.agent"


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _plist_content() -> str:
    project_dir = Path(__file__).resolve().parent.parent.parent
    if getattr(sys, "frozen", False):
        # PyInstaller / .app 打包：sys.executable 即可执行自身
        prog_args = f"        <string>{sys.executable}</string>"
        workdir = str(Path(sys.executable).parent)
    else:
        gui = project_dir / "voice_input_gui.py"
        prog_args = (f"        <string>{sys.executable}</string>\n"
                     f"        <string>{gui}</string>")
        workdir = str(project_dir)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>
    <key>ProgramArguments</key>
    <array>
{prog_args}
    </array>
    <key>WorkingDirectory</key>
    <string>{workdir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""


def set_autostart(enabled: bool) -> None:
    p = _plist_path()
    if enabled:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_plist_content(), encoding="utf-8")
        subprocess.run(["launchctl", "load", str(p)], capture_output=True, text=True)
        logger.info("LaunchAgent loaded: %s", p)
    else:
        if p.exists():
            subprocess.run(["launchctl", "unload", str(p)], capture_output=True, text=True)
            try:
                p.unlink()
            except FileNotFoundError:
                pass
            logger.info("LaunchAgent unloaded: %s", p)


def is_enabled() -> bool:
    return _plist_path().exists()


# 兼容旧接口
def enable_service() -> None:
    set_autostart(True)


def disable_service() -> None:
    set_autostart(False)
