"""Windows 开机自启后端：在「启动」文件夹放一个 .bat 启动脚本。

启动文件夹路径：
%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup
登录时该目录下的项会被自动执行，无需管理员权限。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

APP_NAME = "VoiceInput"


def _startup_dir() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _startup_file() -> Path:
    return _startup_dir() / f"{APP_NAME}.bat"


def _launch_command() -> str:
    # chcp 65001 切到 UTF-8 代码页，避免中文路径在默认 GBK 代码页下乱码
    if getattr(sys, "frozen", False):
        # PyInstaller 打包：sys.executable 即 voice-input.exe，直接跑自身
        return f'@echo off\r\nchcp 65001 >nul\r\nstart "" "{sys.executable}"\r\n'
    # 源码版：pythonw 无控制台窗口；venv 的 Scripts 下通常没有 pythonw.exe，
    # 回退到 base 解释器目录，避免开机自启时弹出黑色 CMD 窗口。
    project_dir = Path(__file__).resolve().parent.parent.parent
    gui = project_dir / "voice_input_gui.py"
    pyw = Path(sys.executable).with_name("pythonw.exe")
    if not pyw.exists():
        pyw = Path(sys.base_prefix) / "pythonw.exe"
    runner = str(pyw) if pyw.exists() else sys.executable
    return f'@echo off\r\nchcp 65001 >nul\r\nstart "" "{runner}" "{gui}"\r\n'


def set_autostart(enabled: bool) -> None:
    f = _startup_file()
    if enabled:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(_launch_command(), encoding="utf-8")
        logger.info("startup file written: %s", f)
    else:
        try:
            f.unlink()
            logger.info("startup file removed: %s", f)
        except FileNotFoundError:
            pass


def is_enabled() -> bool:
    return _startup_file().exists()


# 兼容旧接口
def enable_service() -> None:
    set_autostart(True)


def disable_service() -> None:
    set_autostart(False)
