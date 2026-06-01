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

ICON_SIZE = 128  # 高分辨率，缩放后更清晰

# 缓存目录
CACHE_DIR = Path(
    os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "voice-input" / "icons"

# 状态色（背景统一深灰，麦克风颜色按状态变）
BG_COLOR = (52, 56, 68)          # 深灰
BG_OUTLINE = (75, 80, 95)        # 比背景稍亮一点的描边

COLORS = {
    "idle":       (235, 235, 240),   # 白色
    "recording":  (235, 70, 70),     # 红色
    "processing": (80, 160, 240),    # 蓝色
    "error":      (240, 130, 50),    # 橙色
    "paused":     (140, 140, 150),   # 灰色
}

# 录音状态外圈
RING_COLOR = (235, 70, 70, 180)


def _draw_microphone(
    state: str,
    bg_color: tuple[int, int, int] = BG_COLOR,
) -> Image.Image:
    """绘制麦克风图标"""
    mic_color = COLORS[state]
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 1. 圆形背景
    pad = 4
    d.ellipse(
        (pad, pad, ICON_SIZE - pad, ICON_SIZE - pad),
        fill=bg_color + (255,),
        outline=BG_OUTLINE + (255,),
        width=2,
    )

    cx = ICON_SIZE // 2

    # 2. 录音状态：背景加一圈外环
    if state == "recording":
        d.ellipse(
            (pad - 2, pad - 2, ICON_SIZE - pad + 2, ICON_SIZE - pad + 2),
            outline=RING_COLOR,
            width=4,
        )

    # 3. 麦克风胶囊体
    mic_w, mic_h = 36, 52
    mic_x0 = cx - mic_w // 2
    mic_y0 = 28
    mic_x1 = cx + mic_w // 2
    mic_y1 = mic_y0 + mic_h
    d.rounded_rectangle(
        (mic_x0, mic_y0, mic_x1, mic_y1),
        radius=mic_w // 2,
        fill=mic_color + (255,),
    )

    # 4. U 型托架
    arc_w = 60
    arc_x0 = cx - arc_w // 2
    arc_y0 = mic_y1 - 26
    d.arc(
        (arc_x0, arc_y0, arc_x0 + arc_w, arc_y0 + 36),
        start=0, end=180,
        fill=mic_color + (255,),
        width=5,
    )

    # 5. 杆
    pole_y0 = arc_y0 + 30
    d.line((cx, pole_y0, cx, pole_y0 + 12), fill=mic_color + (255,), width=5)

    # 6. 底座
    d.line(
        (cx - 14, pole_y0 + 12, cx + 14, pole_y0 + 12),
        fill=mic_color + (255,),
        width=5,
    )

    # 7. 识别中状态：右下角加 3 个小圆点
    if state == "processing":
        for i, dx in enumerate((-12, 0, 12)):
            d.ellipse(
                (cx + 30 + dx - 4, ICON_SIZE - 30 - 4,
                 cx + 30 + dx + 4, ICON_SIZE - 30 + 4),
                fill=mic_color + (255,),
            )

    # 8. 错误状态：右下角加感叹号
    if state == "error":
        ex = ICON_SIZE - 30
        ey = ICON_SIZE - 30
        d.ellipse((ex - 14, ey - 14, ex + 14, ey + 14), fill=(220, 60, 60, 255))
        d.line((ex, ey - 7, ex, ey + 3), fill=(255, 255, 255), width=3)
        d.ellipse((ex - 2, ey + 5, ex + 2, ey + 9), fill=(255, 255, 255))

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
