"""跨平台文字注入层。

按运行平台自动选择后端：
- Linux  → xdotool + xclip（X11）
- Windows → pyperclip + pynput（Ctrl+V）
- macOS  → pyperclip + pynput（Cmd+V）

对外保持与旧 core/inject.py 一致的接口：
inject_via_paste / inject_via_type / check_deps / is_terminal_window /
detect_active_window_class，新增 get_backend_name 便于调试。
"""

from __future__ import annotations

import sys
from types import ModuleType

from . import linux, macos, windows


def _select_backend(platform: str) -> ModuleType:
    """根据 sys.platform 字符串选择后端模块。未知平台默认 Linux。"""
    if platform.startswith("linux"):
        return linux
    if platform == "win32":
        return windows
    if platform == "darwin":
        return macos
    return linux


_backend = _select_backend(sys.platform)


def inject_via_paste(
    text: str,
    paste_key: str = "ctrl+v",
    terminal_paste_key: str = "ctrl+shift+v",
) -> None:
    return _backend.inject_via_paste(text, paste_key, terminal_paste_key)


def inject_via_type(text: str) -> None:
    return _backend.inject_via_type(text)


def check_deps(input_method: str = "paste") -> list[str]:
    return _backend.check_deps(input_method)


def is_terminal_window() -> bool:
    return _backend.is_terminal_window()


def detect_active_window_class() -> str:
    return _backend.detect_active_window_class()


def get_backend_name() -> str:
    return _backend.get_backend_name()
