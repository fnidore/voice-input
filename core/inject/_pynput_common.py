"""Windows / macOS 共用的注入实现：pyperclip 写剪贴板 + pynput 模拟按键。

所有第三方依赖均在函数内延迟导入，便于在没有 GUI 的环境中做单元测试 mock，
也避免在 import 阶段触发 pynput 对显示后端的连接。
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def clipboard_paste(text: str, modifier_attr: str) -> None:
    """把 text 写进剪贴板，再用 <modifier>+V 触发粘贴，最后恢复原剪贴板。

    modifier_attr: pynput.keyboard.Key 上的属性名，Windows/Linux 用 "ctrl"，macOS 用 "cmd"。
    """
    if not text:
        return

    import pyperclip
    from pynput.keyboard import Controller, Key

    try:
        original = pyperclip.paste()
    except Exception:
        original = ""

    try:
        pyperclip.copy(text)
    except Exception as e:  # pragma: no cover - 真实环境兜底
        logger.error("clipboard copy failed: %s, fallback to type", e)
        type_text(text)
        return

    time.sleep(0.06)

    keyboard = Controller()
    modifier = getattr(Key, modifier_attr)
    keyboard.press(modifier)
    keyboard.press("v")
    keyboard.release("v")
    keyboard.release(modifier)

    time.sleep(0.25)

    try:
        pyperclip.copy(original)
    except Exception:
        pass


def type_text(text: str) -> None:
    """逐字符模拟键入（fallback，中文可能丢字）。"""
    if not text:
        return
    from pynput.keyboard import Controller

    Controller().type(text)


def check_deps(input_method: str = "paste") -> list[str]:
    """Windows/macOS 仅依赖纯 Python 库，返回缺失的库名。"""
    missing: list[str] = []
    try:
        import pyperclip  # noqa: F401
    except Exception:
        missing.append("pyperclip")
    try:
        import pynput  # noqa: F401
    except Exception:
        missing.append("pynput")
    return missing
