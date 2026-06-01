"""Windows 文字注入后端：pyperclip 写剪贴板 + pynput 模拟 Ctrl+V。"""

from __future__ import annotations

from . import _pynput_common as _c


def get_backend_name() -> str:
    return "windows"


def detect_active_window_class() -> str:
    # Windows 不做窗口类检测（统一使用标准粘贴键）
    return ""


def is_terminal_window() -> bool:
    return False


def inject_via_paste(
    text: str,
    paste_key: str = "ctrl+v",
    terminal_paste_key: str = "ctrl+shift+v",
) -> None:
    # Windows Terminal 等也用 Ctrl+V，is_terminal_window 恒为 False，统一走 paste_key
    combo = terminal_paste_key if is_terminal_window() else paste_key
    _c.clipboard_paste(text, combo)


def inject_via_type(text: str) -> None:
    _c.type_text(text)


def check_deps(input_method: str = "paste") -> list[str]:
    return _c.check_deps(input_method)
