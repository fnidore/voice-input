"""跨平台开机自启层。

按运行平台自动选择后端：
- Linux  → systemd user service
- Windows → 「启动」文件夹 .bat
- macOS  → LaunchAgent plist

对外接口与旧 gui/autostart.py 一致：set_autostart / is_enabled
（并保留 enable_service / disable_service 兼容别名）。
"""

from __future__ import annotations

import sys
from types import ModuleType

from . import linux, macos, windows


def _select_backend(platform: str) -> ModuleType:
    if platform.startswith("linux"):
        return linux
    if platform == "win32":
        return windows
    if platform == "darwin":
        return macos
    return linux


_backend = _select_backend(sys.platform)


def set_autostart(enabled: bool) -> None:
    return _backend.set_autostart(enabled)


def is_enabled() -> bool:
    return _backend.is_enabled()


def enable_service() -> None:
    return _backend.set_autostart(True)


def disable_service() -> None:
    return _backend.set_autostart(False)
