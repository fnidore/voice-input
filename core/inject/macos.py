"""macOS 文字注入后端：pyperclip 写剪贴板 + pynput 模拟 Cmd+V。

注意：macOS 需在「系统设置 → 隐私与安全性 → 辅助功能」中授权本程序，
pynput 才能模拟全局按键。
"""

from __future__ import annotations

from . import _pynput_common as _c


def get_backend_name() -> str:
    return "macos"


def detect_active_window_class() -> str:
    return ""


def is_terminal_window() -> bool:
    return False


def inject_via_paste(
    text: str,
    paste_key: str = "ctrl+v",
    terminal_paste_key: str = "ctrl+shift+v",
) -> None:
    combo = terminal_paste_key if is_terminal_window() else paste_key
    # macOS 用 Cmd 代替 Ctrl（配置默认是 ctrl+v，这里统一换成 cmd+v）
    combo = combo.replace("ctrl", "cmd")
    _c.clipboard_paste(text, combo)


def inject_via_type(text: str) -> None:
    _c.type_text(text)


def check_deps(input_method: str = "paste") -> list[str]:
    return _c.check_deps(input_method)
