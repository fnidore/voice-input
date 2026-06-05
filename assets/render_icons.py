#!/usr/bin/env python3
"""把 icon_bg.svg + icon_mic.svg 渲染合成为全平台应用图标。

流程：
  1. QtSvg 离屏渲染两张 SVG 为 1024px PNG（Qt 不支持 SVG 滤镜，故辉光不在 SVG 里做）
  2. Pillow 对麦克风层做高斯模糊叠出青色霓虹辉光，与背景合成
  3. 缩放导出各尺寸 PNG，并打包成 Windows .ico / macOS .icns / 通用 icon.png

用法:  QT_QPA_PLATFORM=offscreen python assets/render_icons.py
依赖:  PySide6（项目已依赖）、Pillow
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402
from PIL import Image, ImageChops, ImageFilter  # noqa: E402

ASSETS = Path(__file__).resolve().parent
MASTER = 1024


def _render_svg(svg_path: Path, size: int) -> Image.Image:
    """QtSvg 渲染单张 SVG 为透明底 PIL RGBA 图。"""
    renderer = QSvgRenderer(str(svg_path))
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    buf = img.constBits().tobytes()
    return Image.frombytes("RGBA", (size, size), buf, "raw", "BGRA")


def _soft_shadow(
    mic: Image.Image,
    radius: int = 30,
    gain: float = 0.45,
    tint: tuple[int, int, int] = (30, 58, 138),
    dy: int = 16,
) -> Image.Image:
    """用麦克风层 alpha 做柔和深蓝投影（轻微下移），替代旧版霓虹辉光。"""
    alpha = mic.split()[3].filter(ImageFilter.GaussianBlur(radius))
    alpha = alpha.point(lambda v: int(v * gain))
    shadow = Image.new("RGBA", mic.size, tint + (0,))
    shadow.putalpha(alpha)
    return ImageChops.offset(shadow, 0, dy)


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841  QtSvg 离屏渲染需要

    bg = _render_svg(ASSETS / "icon_bg.svg", MASTER)
    mic = _render_svg(ASSETS / "icon_mic.svg", MASTER)

    # 柔和投影 + 麦克风（清新简约，不再做霓虹辉光）
    composite = bg.copy()
    composite = Image.alpha_composite(composite, _soft_shadow(mic))
    composite = Image.alpha_composite(composite, mic)

    master_png = ASSETS / "icon_1024.png"
    composite.save(master_png)
    print("✓ 合成主图", master_png)

    # 各尺寸 PNG（LANCZOS 高质量缩放）
    sizes = [16, 32, 48, 64, 128, 256, 512]
    for s in sizes:
        out = ASSETS / f"icon_{s}.png"
        composite.resize((s, s), Image.LANCZOS).save(out)
        print("✓", out.name)

    # 通用图标（Linux 桌面 / 仓库展示）
    composite.resize((512, 512), Image.LANCZOS).save(ASSETS / "icon.png")

    # Windows .ico（多尺寸内嵌）
    ico = ASSETS / "icon.ico"
    composite.resize((256, 256), Image.LANCZOS).save(
        ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print("✓ Windows", ico.name)

    # macOS .icns
    try:
        icns = ASSETS / "icon.icns"
        composite.save(icns)
        print("✓ macOS", icns.name)
    except Exception as exc:  # icns 写入对尺寸敏感，失败不致命
        print("⚠ icns 生成失败（可后续在 mac 上用 iconutil 生成）：", exc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
