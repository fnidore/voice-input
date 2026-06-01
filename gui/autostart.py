"""systemd user service 安装 / 卸载（在 GUI 里通过开关调用）"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SERVICE_NAME = "voice-input.service"
SERVICE_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_FILE = SERVICE_DIR / SERVICE_NAME


def _service_unit_content() -> str:
    """生成 service 文件内容，指向项目里的 run_gui.sh"""
    project_dir = Path(__file__).resolve().parent.parent
    run_script = project_dir / "run_gui.sh"
    return f"""[Unit]
Description=Voice Input (SenseVoice global voice dictation)
After=graphical-session.target sound.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/bin/bash {run_script}
Restart=on-failure
RestartSec=5
# 让 GUI 能连上 X server
Environment=DISPLAY=:1
# 不限制 stdout/stderr，方便 journalctl 查看
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""


def _systemctl_user(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True, text=True,
    )


def install_service() -> None:
    SERVICE_DIR.mkdir(parents=True, exist_ok=True)
    SERVICE_FILE.write_text(_service_unit_content(), encoding="utf-8")
    _systemctl_user("daemon-reload")
    logger.info("service unit written: %s", SERVICE_FILE)


def enable_service() -> None:
    install_service()
    r = _systemctl_user("enable", "--now", SERVICE_NAME)
    if r.returncode != 0:
        raise RuntimeError(f"enable failed: {r.stderr.strip()}")
    logger.info("service enabled and started")


def disable_service() -> None:
    r = _systemctl_user("disable", "--now", SERVICE_NAME)
    if r.returncode != 0:
        # 服务没装也不算错
        if "does not exist" in r.stderr.lower() or "not loaded" in r.stderr.lower():
            return
        raise RuntimeError(f"disable failed: {r.stderr.strip()}")
    logger.info("service disabled")


def set_autostart(enabled: bool) -> None:
    if enabled:
        enable_service()
    else:
        disable_service()


def is_enabled() -> bool:
    r = _systemctl_user("is-enabled", SERVICE_NAME)
    return r.stdout.strip() == "enabled"
