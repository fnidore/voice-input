"""Windows / macOS 共用的注入实现：pyperclip 写剪贴板 + pynput 模拟按键。

所有第三方依赖均在函数内延迟导入，便于在没有 GUI 的环境中做单元测试 mock，
也避免在 import 阶段触发 pynput 对显示后端的连接（这点对 headless CI 很关键）。
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# 粘贴动作发出后，等目标应用真正完成粘贴再恢复剪贴板。
# pynput 的按键是异步事件（不像 xdotool key 同步），Electron/VSCode 等较慢，留足时间。
_PASTE_SETTLE_SECONDS = 0.5

# 修饰键别名 -> pynput.keyboard.Key 上的属性名
_MODIFIER_ALIASES = {
    "ctrl": "ctrl", "control": "ctrl",
    "cmd": "cmd", "command": "cmd", "super": "cmd", "win": "cmd",
    "shift": "shift",
    "alt": "alt", "option": "alt",
}


def _resolve_main_key(token: str, Key):
    """把组合键里的非修饰键 token 解析为 pynput 可用的按键。"""
    token = token.strip()
    if len(token) == 1:
        return token  # 普通字符键，如 "v"
    low = token.lower()
    if hasattr(Key, low):
        return getattr(Key, low)  # 特殊键，如 insert / enter
    return token


def _parse_combo(combo: str, Key):
    """把 'ctrl+shift+v' 解析为 (修饰键列表, 主键)。"""
    modifiers = []
    main = None
    for raw in combo.split("+"):
        token = raw.strip().lower()
        if not token:
            continue
        if token in _MODIFIER_ALIASES:
            modifiers.append(getattr(Key, _MODIFIER_ALIASES[token]))
        else:
            main = _resolve_main_key(raw, Key)
    return modifiers, main


def clipboard_paste(text: str, combo: str = "ctrl+v") -> None:
    """把 text 写进剪贴板，按 combo 组合键触发粘贴，最后恢复原剪贴板。

    combo: 组合键字符串，如 "ctrl+v" / "ctrl+shift+v" / "cmd+v" / "shift+insert"。
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

    modifiers, main = _parse_combo(combo, Key)
    keyboard = Controller()
    for m in modifiers:
        keyboard.press(m)
    if main is not None:
        keyboard.press(main)
        keyboard.release(main)
    for m in reversed(modifiers):
        keyboard.release(m)

    time.sleep(_PASTE_SETTLE_SECONDS)

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
