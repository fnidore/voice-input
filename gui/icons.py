"""动态生成托盘图标（清新简约浅色版）。

三/多态：idle 待机 / recording 录音 / processing 识别中 / error 错误 / paused 暂停。
造型：浅色圆角磁贴 + 线性麦克风（状态变色）+ 右上角状态点。

保存为 PNG 文件后用 QIcon(filepath) 创建
—— GNOME AppIndicator 必须文件路径才能稳定显示。

公开 API 与旧版一致：icon_idle/recording/processing/error/paused + regenerate_all。
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw
from PySide6.QtGui import QIcon

try:
    from .style import PALETTE
except Exception:  # 允许脱离包单测
    PALETTE = {"rec": "#ef6c54", "proc": "#e8a13a", "error": "#e0584f", "idle": "#99a0b0",
               "surface": "#ffffff", "border_2": "#dde0e7", "bg": "#f1f4f8"}

ICON_SIZE = 256
S = ICON_SIZE / 1024.0

CACHE_DIR = Path(
    os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "voice-input" / "icons"


def _rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# 浅色磁贴
TILE_FILL = _rgb(PALETTE["surface"])      # 白
TILE_EDGE = _rgb(PALETTE["border_2"])     # 浅灰描边
GRILLE = (210, 216, 226)                  # 话筒音格线（极浅）

# 状态 → 麦克风主色
COLORS = {
    "idle":       _rgb(PALETTE["idle"]),    # 灰
    "recording":  _rgb(PALETTE["rec"]),     # 珊瑚
    "processing": _rgb(PALETTE["proc"]),    # 琥珀
    "error":      _rgb(PALETTE["error"]),   # 红
    "paused":     (192, 197, 208),          # 浅灰
}
# 哪些状态显示右上角状态点
DOT_STATES = {"recording", "processing", "error"}


def _sx(v: float) -> float:
    return v * S


def _draw_mic(d: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    """线性麦克风（与 app 图标同款几何，描边版）。"""
    c = color + (255,)
    w = max(2, round(34 * S))

    # 话筒头胶囊（描边）
    d.rounded_rectangle(
        (_sx(404), _sx(228), _sx(620), _sx(602)), radius=_sx(108),
        outline=c, width=w,
    )
    # 支架 U 弧 + 两端竖线
    d.arc((_sx(306), _sx(288), _sx(718), _sx(700)), start=0, end=180, fill=c, width=w)
    d.line((_sx(306), _sx(454), _sx(306), _sx(494)), fill=c, width=w)
    d.line((_sx(718), _sx(454), _sx(718), _sx(494)), fill=c, width=w)
    # 底杆 + 底座
    d.line((_sx(512), _sx(700), _sx(512), _sx(818)), fill=c, width=w)
    d.line((_sx(396), _sx(830), _sx(628), _sx(830)), fill=c, width=w)
    # 音格线（浅）
    gw = max(1, round(15 * S))
    for gy in (322, 378, 434):
        d.line((_sx(452), _sx(gy), _sx(572), _sx(gy)), fill=GRILLE + (255,), width=gw)


def _draw_icon(state: str) -> Image.Image:
    mic_color = COLORS[state]
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = max(2, round(ICON_SIZE * 0.045))
    radius = round(ICON_SIZE * 0.27)
    # 浅色圆角磁贴
    d.rounded_rectangle(
        (pad, pad, ICON_SIZE - pad, ICON_SIZE - pad), radius=radius,
        fill=TILE_FILL + (255,), outline=TILE_EDGE + (255,),
        width=max(1, round(ICON_SIZE * 0.012)),
    )

    _draw_mic(d, mic_color)

    # 右上角状态点（带磁贴底色的描边环，像“突出”在角上）
    if state in DOT_STATES:
        cx, cy = round(ICON_SIZE * 0.78), round(ICON_SIZE * 0.22)
        r = round(ICON_SIZE * 0.105)
        ring = max(2, round(ICON_SIZE * 0.03))
        d.ellipse((cx - r - ring, cy - r - ring, cx + r + ring, cy + r + ring),
                  fill=TILE_FILL + (255,))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=mic_color + (255,))
        # error 状态：点内画白色感叹号
        if state == "error":
            lw = max(2, round(ICON_SIZE * 0.022))
            d.line((cx, cy - round(r * 0.42), cx, cy + round(r * 0.12)),
                   fill=(255, 255, 255, 255), width=lw)
            dot = max(1, round(lw * 0.6))
            dy = cy + round(r * 0.46)
            d.ellipse((cx - dot, dy - dot, cx + dot, dy + dot), fill=(255, 255, 255, 255))

    return img


_ICON_CACHE: dict[str, QIcon] = {}


def _get_icon(state: str) -> QIcon:
    if state in _ICON_CACHE:
        return _ICON_CACHE[state]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"voice-input-{state}.png"
    _draw_icon(state).save(path, format="PNG")
    ic = QIcon(str(path))
    _ICON_CACHE[state] = ic
    return ic


def icon_idle() -> QIcon:
    return _get_icon("idle")


def icon_recording() -> QIcon:
    return _get_icon("recording")


def icon_processing() -> QIcon:
    return _get_icon("processing")


def icon_error() -> QIcon:
    return _get_icon("error")


def icon_paused() -> QIcon:
    return _get_icon("paused")


def regenerate_all() -> None:
    """强制重新生成所有图标（调试用）。"""
    _ICON_CACHE.clear()
    for state in COLORS:
        _get_icon(state)
