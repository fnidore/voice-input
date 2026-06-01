"""Linux/X11 文字注入后端：剪贴板粘贴（xclip + xdotool） / xdotool type。

行为与重构前的 core/inject.py 完全一致，专为 X11 桌面环境。
"""

from __future__ import annotations

import logging
import re
import subprocess
import time

logger = logging.getLogger(__name__)

# 常见终端的 WM_CLASS（小写），用 Shift+Ctrl+V 系列粘贴
TERMINAL_CLASSES: frozenset[str] = frozenset({
    # 传统 X11 终端
    "gnome-terminal", "gnome-terminal-server",
    "xterm", "uxterm",
    "konsole",
    "alacritty",
    "kitty",
    "terminator",
    "tilix",
    "wezterm", "org.wezfurlong.wezterm",
    "xfce4-terminal",
    "deepin-terminal",
    "tilda", "guake",
    "qterminal",
    "warp-terminal",
    "io.elementary.terminal",
    # Electron / Web 技术栈终端
    "tabby",
    "hyper",
    "extraterm",
    "rio",
})

_WM_CLASS_RE = re.compile(r'"([^"]+)"')


def get_backend_name() -> str:
    return "linux"


def detect_active_window_class() -> str:
    """返回焦点窗口的 WM_CLASS（小写），失败返回空串"""
    # 方案 A: xdotool getwindowclassname (新版本)
    try:
        r = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowclassname"],
            capture_output=True, text=True, timeout=1,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().lower()
    except Exception:
        pass
    # 方案 B: xprop 兜底
    try:
        wid = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=1,
        ).stdout.strip()
        if not wid:
            return ""
        r = subprocess.run(
            ["xprop", "-id", wid, "WM_CLASS"],
            capture_output=True, text=True, timeout=1,
        )
        if "=" in r.stdout:
            vals = _WM_CLASS_RE.findall(r.stdout.split("=", 1)[1])
            if vals:
                return vals[-1].lower()
    except Exception:
        pass
    return ""


def is_terminal_window() -> bool:
    cls = detect_active_window_class()
    if not cls:
        return False
    if cls in TERMINAL_CLASSES:
        return True
    return "term" in cls


def _xclip_set(selection: str, data: bytes) -> None:
    subprocess.run(
        ["xclip", "-selection", selection],
        input=data, timeout=2, check=False,
    )


def inject_via_paste(
    text: str,
    paste_key: str = "ctrl+v",
    terminal_paste_key: str = "ctrl+shift+v",
) -> None:
    """剪贴板 + 自动适配粘贴键（中文最稳）"""
    if not text:
        return
    try:
        orig_clip = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, timeout=1,
        ).stdout
    except Exception:
        orig_clip = b""

    try:
        _xclip_set("clipboard", text.encode("utf-8"))
        _xclip_set("primary", text.encode("utf-8"))
    except Exception as e:
        logger.error("write clipboard failed: %s, fallback to type", e)
        inject_via_type(text)
        return

    time.sleep(0.06)

    cls = detect_active_window_class()
    in_term = bool(cls) and (cls in TERMINAL_CLASSES or "term" in cls)
    chosen = terminal_paste_key if in_term else paste_key
    logger.debug("paste: class=%r is_term=%s key=%s", cls, in_term, chosen)

    subprocess.run(
        ["xdotool", "key", "--clearmodifiers", chosen],
        check=False,
    )

    time.sleep(0.25)
    _xclip_set("clipboard", orig_clip)


def inject_via_type(text: str) -> None:
    """xdotool type，中文快速输入容易丢字，仅 fallback"""
    if not text:
        return
    subprocess.run(
        ["xdotool", "type", "--delay", "12", "--clearmodifiers", text],
        check=False,
    )


def check_deps(input_method: str = "paste") -> list[str]:
    """返回缺失的系统依赖名列表"""
    missing = []
    for tool in ("xdotool", "xprop"):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            missing.append(tool)
    if input_method == "paste":
        if subprocess.run(["which", "xclip"], capture_output=True).returncode != 0:
            missing.append("xclip")
    return missing
