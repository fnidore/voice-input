"""动态生成托盘图标（三态：待机/录音/识别中/错误）

设计要点:
1. 圆形深色背景 + 内部麦克风，扁平化现代风
2. 保存为 PNG 文件后用 QIcon(filepath) 创建
   —— GNOME AppIndicator 必须文件路径才能稳定显示，QPixmap 内存图会被替换
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from PySide6.QtGui import QIcon

ICON_SIZE = 256  # 高分辨率渲染，托盘缩放后更清晰
S = ICON_SIZE / 1024.0  # 复用 app 图标的 1024 画布坐标，按此系数缩放，造型保持一致

# 缓存目录
CACHE_DIR = Path(
    os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "voice-input" / "icons"

# 深色圆底（呼应 app 图标的深蓝近黑霓虹风）
BG_COLOR = (10, 15, 31)          # #0a0f1f 深蓝近黑
BG_OUTLINE = (34, 211, 238)      # 青色描边（半透明叠加）
GRILLE_COLOR = (6, 16, 31)       # 话筒音格线（深色镂空感）

# 状态 → 麦克风霓虹主色
COLORS = {
    "idle":       (34, 211, 238),    # 青 cyan —— 待机
    "recording":  (255, 59, 107),    # 玫红 —— 录音
    "processing": (251, 191, 36),    # 琥珀黄 —— 识别中
    "error":      (239, 68, 68),     # 红 —— 错误
    "paused":     (148, 163, 184),   # 灰 —— 暂停
}


def _sx(v: float) -> float:
    """1024 画布坐标 → 当前 ICON_SIZE 坐标。"""
    return v * S


def _mic_layer(color: tuple[int, int, int]) -> Image.Image:
    """在透明层上画麦克风造型（与 app 图标同款几何），返回 RGBA 图。"""
    layer = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = color + (255,)
    w = max(2, round(34 * S))  # 支架 / 杆 / 座线宽

    # 话筒头胶囊
    d.rounded_rectangle(
        (_sx(404), _sx(228), _sx(620), _sx(602)), radius=_sx(108), fill=c
    )
    # 支架 U 弧（下半圆）+ 两端竖线
    d.arc((_sx(306), _sx(288), _sx(718), _sx(700)), start=0, end=180, fill=c, width=w)
    d.line((_sx(306), _sx(454), _sx(306), _sx(494)), fill=c, width=w)
    d.line((_sx(718), _sx(454), _sx(718), _sx(494)), fill=c, width=w)
    # 底杆 + 底座
    d.line((_sx(512), _sx(700), _sx(512), _sx(818)), fill=c, width=w)
    d.line((_sx(396), _sx(830), _sx(628), _sx(830)), fill=c, width=w)
    # grille 音格线
    gw = max(1, round(15 * S))
    for gy in (322, 378, 434):
        d.line((_sx(436), _sx(gy), _sx(588), _sx(gy)), fill=GRILLE_COLOR + (190,), width=gw)
    return layer


def _draw_microphone(
    state: str,
    bg_color: tuple[int, int, int] = BG_COLOR,
) -> Image.Image:
    """绘制托盘图标：深色圆底 + 霓虹麦克风 + 辉光，状态变色。"""
    mic_color = COLORS[state]
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = max(2, round(ICON_SIZE * 0.03))
    # 深色圆底 + 青色细描边
    d.ellipse(
        (pad, pad, ICON_SIZE - pad, ICON_SIZE - pad),
        fill=bg_color + (255,),
        outline=BG_OUTLINE + (90,),
        width=max(1, round(ICON_SIZE * 0.012)),
    )

    # 录音态：外圈高亮环
    if state == "recording":
        r = max(2, round(ICON_SIZE * 0.022))
        d.ellipse(
            (pad - r, pad - r, ICON_SIZE - pad + r, ICON_SIZE - pad + r),
            outline=mic_color + (210,),
            width=r,
        )

    # 麦克风 + 霓虹辉光（高斯模糊叠加，呼应 app 图标）
    mic = _mic_layer(mic_color)
    glow = mic.filter(ImageFilter.GaussianBlur(max(2, round(ICON_SIZE / 16))))
    gr, gg, gb, ga = glow.split()
    ga = ga.point(lambda v: min(255, int(v * 1.8)))
    glow = Image.merge("RGBA", (gr, gg, gb, ga))
    img = Image.alpha_composite(img, glow)
    img = Image.alpha_composite(img, mic)

    d = ImageDraw.Draw(img)
    # 识别中：右下三个小圆点
    if state == "processing":
        dr = round(ICON_SIZE * 0.030)
        dy = round(ICON_SIZE * 0.80)
        for fx in (0.58, 0.69, 0.80):
            x = round(ICON_SIZE * fx)
            d.ellipse((x - dr, dy - dr, x + dr, dy + dr), fill=mic_color + (255,))

    # 错误：右下红色感叹号徽标
    if state == "error":
        ex, ey = round(ICON_SIZE * 0.75), round(ICON_SIZE * 0.75)
        rr = round(ICON_SIZE * 0.12)
        d.ellipse((ex - rr, ey - rr, ex + rr, ey + rr), fill=(239, 68, 68, 255))
        lw = max(2, round(ICON_SIZE * 0.024))
        d.line((ex, ey - round(rr * 0.5), ex, ey + round(rr * 0.12)),
               fill=(255, 255, 255, 255), width=lw)
        dotr = max(1, round(lw * 0.55))
        dy2 = ey + round(rr * 0.42)
        d.ellipse((ex - dotr, dy2 - dotr, ex + dotr, dy2 + dotr),
                  fill=(255, 255, 255, 255))

    return img


_ICON_CACHE: dict[str, QIcon] = {}


def _get_icon(state: str) -> QIcon:
    """生成/缓存图标，返回 QIcon(文件路径)"""
    if state in _ICON_CACHE:
        return _ICON_CACHE[state]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"voice-input-{state}.png"

    # 缓存文件不存在或我们要重新生成
    img = _draw_microphone(state)
    img.save(path, format="PNG")

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
    """强制重新生成所有图标（调试用）"""
    _ICON_CACHE.clear()
    for state in COLORS:
        _get_icon(state)
