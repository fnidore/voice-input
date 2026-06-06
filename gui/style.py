"""「柔和卡片」主题 · 浅 / 深双套 token（与设计稿 tokens.css 一一对应）。

- LIGHT / DARK：两套调色板；palette() 返回当前主题的那套
- set_theme("light"|"dark")：切换并持久化（QSettings VoiceInput/ui）
- apply_soft_theme(widget)：按当前主题套 QSS
- PALETTE：恒为浅色（托盘图标 / 兼容旧引用）

只负责样式，不含业务逻辑。
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSettings

_UI_CACHE = Path(
    os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "voice-input" / "ui"

# ---- 设计 token（对应 tokens.css）----
LIGHT = {
    "bg":            "#ffffff",
    "surface":       "#ffffff",
    "surface_2":     "#f6f7f9",
    "surface_3":     "#eef0f3",
    "inset":         "#f3f5f8",   # variant-b 画布
    "text":          "#1b1e25",
    "text_2":        "#5a6071",
    "text_3":        "#99a0b0",
    "border":        "#e8eaef",
    "border_2":      "#dde0e7",
    "accent":        "#5b8def",
    "accent_press":  "#3f72db",
    "accent_tint":   "rgba(91, 141, 239, 12%)",
    "accent_tint_2": "rgba(91, 141, 239, 6%)",
    "on_accent":     "#ffffff",
    "win_border":    "rgba(24, 33, 56, 7%)",
    "ok":            "#3aa67b",
    "ok_tint":       "rgba(58, 166, 123, 14%)",
    # 状态色（浅深共用，柔和调）
    "rec":   "#ef6c54",
    "proc":  "#e8a13a",
    "done":  "#5b8def",
    "error": "#e0584f",
    "idle":  "#99a0b0",
}

DARK = {
    "bg":            "#14161b",
    "surface":       "#1a1d24",
    "surface_2":     "#1f232c",
    "surface_3":     "#262b35",
    "inset":         "#15181e",
    "text":          "#e8eaef",
    "text_2":        "#9aa1b1",
    "text_3":        "#646b7c",
    "border":        "#2a2f3a",
    "border_2":      "#333a47",
    "accent":        "#6f97f2",
    "accent_press":  "#5b86ec",
    "accent_tint":   "rgba(111, 151, 242, 16%)",
    "accent_tint_2": "rgba(111, 151, 242, 8%)",
    "on_accent":     "#0f1115",
    "win_border":    "rgba(255, 255, 255, 8%)",
    "ok":            "#56c896",
    "ok_tint":       "rgba(58, 166, 123, 14%)",
    "rec":   "#ef6c54",
    "proc":  "#e8a13a",
    "done":  "#6f97f2",
    "error": "#e0584f",
    "idle":  "#646b7c",
}

# 托盘图标 / 旧模块兼容：恒浅色
PALETTE = LIGHT

# 字体栈（Manrope 装了就用，否则回退系统中英文）
FONT_UI = ('"Manrope", "PingFang SC", "Microsoft YaHei", '
           '"Noto Sans CJK SC", "Segoe UI", -apple-system, sans-serif')
FONT_MONO = ('"JetBrains Mono", "SF Mono", "Cascadia Code", '
             '"Roboto Mono", Menlo, Consolas, monospace')

_settings = QSettings("VoiceInput", "ui")
_theme: str = str(_settings.value("theme", "light"))


def current_theme() -> str:
    return _theme


def set_theme(name: str) -> None:
    """切换主题并持久化。调用方需自行重新 apply_soft_theme + 刷新自绘控件。"""
    global _theme
    _theme = "dark" if name == "dark" else "light"
    _settings.setValue("theme", _theme)


def palette() -> dict:
    """当前主题调色板。自绘控件请在 paintEvent 里实时取色。"""
    return DARK if _theme == "dark" else LIGHT


def _arrow_url(P: dict) -> str:
    """生成（并缓存）下拉箭头 chevron PNG，返回 QSS image 片段。"""
    try:
        path = _UI_CACHE / f"chevron_{_theme}.png"
        if not path.exists():
            _UI_CACHE.mkdir(parents=True, exist_ok=True)
            from .line_icons import icon_pixmap  # 延迟 import，避免无 QApplication 时加载
            icon_pixmap("chevron-down", 12, P["text_3"], stroke=2.2, dpr=1.0).save(str(path))
        return f"image: url({path.as_posix()}); width: 12px; height: 12px;"
    except Exception:
        return ""   # 回退：无箭头图片，仅保留点击区域


def _qss(P: dict) -> str:
    return f"""
* {{ font-family: {FONT_UI}; outline: none; }}

/* ============ 无边框窗体外壳 ============ */
QFrame#shell {{
    background: {P['surface']};
    border: 1px solid {P['win_border']};
    border-radius: 16px;
}}
QFrame#titlebar {{
    background: {P['surface']};
    border-bottom: 1px solid {P['border']};
    border-top-left-radius: 16px; border-top-right-radius: 16px;
}}
QLabel#winTitle {{ font-size: 14px; font-weight: 600; color: {P['text']}; background: transparent; }}

/* 标题栏窗口按钮（最小化/关闭） */
QPushButton[winBtn="true"] {{
    border: none; background: transparent; border-radius: 7px;
    min-width: 30px; max-width: 30px; min-height: 26px; max-height: 26px; padding: 0;
}}
QPushButton[winBtn="true"]:hover {{ background: {P['surface_3']}; }}
QPushButton#winClose:hover {{ background: rgba(224, 88, 79, 16%); }}

/* 主题切换（☀/☾ 分段） */
QFrame#themeToggle {{
    background: {P['surface_2']}; border: 1px solid {P['border']}; border-radius: 9px;
}}
QPushButton[themeBtn="true"] {{
    border: none; background: transparent; border-radius: 6px;
    min-width: 28px; max-width: 28px; min-height: 22px; max-height: 22px; padding: 0;
}}
QPushButton[themeBtn="true"][on="true"] {{ background: {P['surface']}; }}

/* ============ 顶部分段导航 ============ */
QFrame#topnav {{ background: {P['surface']}; border-bottom: 1px solid {P['border']}; }}
QFrame#segSlot {{
    background: {P['surface_2']}; border: 1px solid {P['border']}; border-radius: 11px;
}}
QPushButton[segItem="true"] {{
    border: none; background: transparent; color: {P['text_2']};
    font-size: 13px; font-weight: 600; padding: 8px 15px; border-radius: 8px;
}}
QPushButton[segItem="true"]:hover {{ color: {P['text']}; }}
QPushButton[segItem="true"][segOn="true"] {{ background: {P['surface']}; color: {P['accent']}; }}

/* ============ 画布与卡片 ============ */
QScrollArea#pageScroll {{ background: {P['inset']}; border: none; }}
QScrollArea#pageScroll > QWidget > QWidget {{ background: transparent; }}
QWidget#pageCanvas {{ background: {P['inset']}; }}
QFrame[vi="card"] {{
    background: {P['surface']}; border: 1px solid {P['border']}; border-radius: 16px;
}}
QLabel[vi="cardTitle"] {{ font-size: 14px; font-weight: 700; color: {P['text']}; background: transparent; }}
QLabel[vi="cardDesc"]  {{ font-size: 12px; color: {P['text_3']}; background: transparent; }}

/* 字段 */
QLabel[vi="fieldLabel"] {{ font-size: 13px; font-weight: 600; color: {P['text']}; background: transparent; }}
QLabel[vi="hint"] {{ font-size: 12px; color: {P['text_3']}; background: transparent; }}
QLabel[vi="hintMono"] {{
    font-family: {FONT_MONO}; font-size: 11px; color: {P['text_3']}; background: transparent;
}}
QLabel[vi="togTitle"] {{ font-size: 13px; font-weight: 600; color: {P['text']}; background: transparent; }}
QLabel[vi="togDesc"]  {{ font-size: 12px; color: {P['text_3']}; background: transparent; }}
QLabel {{ background: transparent; color: {P['text']}; }}

/* 弹窗（系统深色模式下原生背景可能与主题文字色冲突，显式锁定） */
QMessageBox {{ background: {P['surface']}; }}
QMessageBox QLabel {{ color: {P['text']}; background: transparent; }}

/* 徽章 pill */
QLabel[vi="pill"] {{
    background: {P['accent_tint']}; color: {P['accent']};
    font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 10px;
}}
QLabel[vi="pillOk"] {{
    background: {P['ok_tint']}; color: {P['ok']};
    font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 10px;
}}
QLabel[vi="pillWarn"] {{
    background: rgba(232, 161, 58, 14%); color: {P['proc']};
    font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 10px;
}}

/* 键帽 keycap */
QLabel[vi="keycap"] {{
    font-family: {FONT_MONO}; font-size: 13px; font-weight: 600; color: {P['text']};
    background: {P['surface']}; border: 1px solid {P['border_2']};
    border-bottom: 2px solid {P['border_2']}; border-radius: 7px; padding: 6px 12px;
}}
QLabel[vi="keycapBig"] {{
    font-family: {FONT_MONO}; font-size: 18px; font-weight: 600; color: {P['text']};
    background: {P['surface']}; border: 1px solid {P['border_2']};
    border-bottom: 2px solid {P['border_2']}; border-radius: 9px; padding: 12px 22px;
}}

/* ============ 输入类控件 ============ */
QComboBox, QLineEdit, QPlainTextEdit, QTextEdit, QDoubleSpinBox, QSpinBox {{
    background: {P['surface']}; color: {P['text']}; font-size: 13px;
    border: 1px solid {P['border_2']}; border-radius: 10px;
    padding: 10px 13px;
    selection-background-color: {P['accent']}; selection-color: {P['on_accent']};
}}
QComboBox:hover, QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover {{ border-color: {P['accent']}; }}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QDoubleSpinBox:focus, QSpinBox:focus {{ border-color: {P['accent']}; }}
QComboBox::drop-down {{ border: none; width: 30px; }}
QComboBox::down-arrow {{ {_arrow_url(P)} margin-right: 13px; }}
QComboBox QAbstractItemView {{
    background: {P['surface']}; color: {P['text']};
    border: 1px solid {P['border_2']}; border-radius: 10px;
    selection-background-color: {P['accent']}; selection-color: {P['on_accent']};
    outline: none; padding: 4px;
}}
QComboBox:disabled, QLineEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {P['text_3']}; background: {P['surface_2']}; border-color: {P['border']};
}}

/* 日志框（mono） */
QTextEdit[vi="log"] {{
    font-family: {FONT_MONO}; font-size: 12px;
    background: {P['inset']}; color: {P['text_2']};
    border: 1px solid {P['border']}; border-radius: 10px; padding: 10px 12px;
}}

/* ============ 按钮 ============ */
QPushButton {{
    background: {P['surface']}; color: {P['text']}; font-size: 13px; font-weight: 600;
    border: 1px solid {P['border_2']}; border-radius: 10px; padding: 9px 16px;
}}
QPushButton:hover {{ border-color: {P['accent']}; color: {P['accent']}; }}
QPushButton:pressed {{ background: {P['accent_tint']}; }}
QPushButton:disabled {{ color: {P['text_3']}; border-color: {P['border']}; background: {P['surface_2']}; }}
QPushButton#primary {{ background: {P['accent']}; color: {P['on_accent']}; border-color: {P['accent']}; }}
QPushButton#primary:hover {{ background: {P['accent_press']}; border-color: {P['accent_press']}; color: {P['on_accent']}; }}
QPushButton#primary:disabled {{ background: {P['surface_3']}; color: {P['text_3']}; border-color: {P['border']}; }}
QPushButton[ghost="true"] {{ background: transparent; border-color: transparent; color: {P['text_2']}; }}
QPushButton[ghost="true"]:hover {{ background: {P['surface_2']}; color: {P['text']}; }}

/* 热词 chip 的 × 按钮 */
QPushButton[chipX="true"] {{
    border: none; background: transparent; border-radius: 9px;
    min-width: 18px; max-width: 18px; min-height: 18px; max-height: 18px; padding: 0;
}}
QPushButton[chipX="true"]:hover {{ background: {P['surface_3']}; }}

/* ============ 滑杆 ============ */
QSlider::groove:horizontal {{
    height: 4px; border-radius: 2px; background: {P['surface_3']};
}}
QSlider::sub-page:horizontal {{ background: {P['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
    background: {P['accent']}; border: 2px solid {P['surface']};
}}

/* ============ 进度条（GPU 运行时下载） ============ */
QProgressBar {{
    height: 8px; border: none; border-radius: 4px; background: {P['surface_3']};
}}
QProgressBar::chunk {{ background: {P['accent']}; border-radius: 4px; }}

/* ============ 热词 chip ============ */
QFrame[vi="chip"] {{
    background: {P['surface_2']}; border: 1px solid {P['border']}; border-radius: 14px;
}}
QLabel[vi="chipText"] {{ font-size: 13px; font-weight: 500; color: {P['text']}; background: transparent; }}
QLineEdit[vi="chipInput"] {{
    border: 1px dashed {P['border_2']}; background: transparent;
    border-radius: 14px; padding: 5px 12px; font-size: 13px; color: {P['text']};
}}
QLineEdit[vi="chipInput"]:focus {{ border: 1px dashed {P['accent']}; }}

/* ============ 历史行 ============ */
QFrame[vi="histRow"] {{ background: transparent; border-radius: 10px; border: none; }}
QFrame[vi="histRow"]:hover {{ background: {P['surface_2']}; }}
QLabel[vi="histMeta"] {{
    font-family: {FONT_MONO}; font-size: 11px; color: {P['text_3']}; background: transparent;
}}
QLabel[vi="histText"] {{ font-size: 13px; color: {P['text']}; background: transparent; }}

/* ============ 底栏 ============ */
QFrame#footer {{
    background: {P['surface']}; border-top: 1px solid {P['border']};
    border-bottom-left-radius: 16px; border-bottom-right-radius: 16px;
}}

/* ============ 滚动条 ============ */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 3px; }}
QScrollBar::handle:vertical {{ background: {P['surface_3']}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {P['border_2']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 3px; }}
QScrollBar::handle:horizontal {{ background: {P['surface_3']}; border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ============ 菜单 / 提示 ============ */
QMenu {{
    background: {P['surface']}; color: {P['text']};
    border: 1px solid {P['border_2']}; border-radius: 12px; padding: 6px;
}}
QMenu::item {{ padding: 8px 22px; border-radius: 8px; font-size: 13px; }}
QMenu::item:selected {{ background: {P['accent_tint']}; color: {P['accent']}; }}
QMenu::item:disabled {{ color: {P['text_3']}; }}
QMenu::separator {{ height: 1px; background: {P['border']}; margin: 5px 8px; }}
QToolTip {{
    background: {P['surface']}; color: {P['text']};
    border: 1px solid {P['border_2']}; border-radius: 6px; padding: 5px 8px;
}}

/* 微调按钮 */
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {{
    width: 20px; background: {P['surface_2']}; border: none; border-radius: 5px;
}}
"""


def apply_soft_theme(widget) -> None:
    """按当前主题给窗口套「柔和卡片」QSS。"""
    widget.setStyleSheet(_qss(palette()))


def themed_msgbox(kind: str, title: str, text: str, parent=None) -> int:
    """主题化 QMessageBox（kind: info / warning / critical）。

    parent=None 的弹窗继承不到任何窗口 QSS，Windows 系统深色模式下
    会出现黑底黑字，这里统一显式套主题。
    """
    from PySide6.QtWidgets import QMessageBox  # 延迟 import，避免循环依赖
    icons = {
        "info": QMessageBox.Information,
        "warning": QMessageBox.Warning,
        "critical": QMessageBox.Critical,
    }
    box = QMessageBox(parent)
    box.setIcon(icons[kind])
    box.setWindowTitle(title)
    box.setText(text)
    apply_soft_theme(box)
    return box.exec()


# 兼容旧入口
def apply_neon_theme(widget) -> None:
    apply_soft_theme(widget)


NEON_QSS = ""
