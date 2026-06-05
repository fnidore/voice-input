"""设置窗口：基础 / 快捷键 / 热词 / 历史 / 日志

「柔和卡片」B 方向 1:1 落地（对应设计稿 settings_b.jsx）：
无边框自绘标题栏（品牌标 + ☀/☾ 主题切换）→ 顶部居中分段 Tab（带图标）
→ 冷灰画布上的分组卡片 → 白色底栏（保存主按钮）。
业务逻辑与旧版一致：保存、预设切换、麦克风测试、历史、日志刷新。
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSlider,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.audio import Recorder
from core.config import Config, LOG_DIR
from core.history import History
from core.presets import PRESETS, get_preset, model_cache_path

from . import line_icons
from .hotkey_capture import HotkeyCaptureButton
from .style import apply_soft_theme, current_theme, palette, set_theme
from .volume_meter import BarMeter
from .widgets import (
    Card, ChipFlow, HSep, IconBadge, SegmentedControl, ToggleSwitch,
    field_label, hint_label, pill_label, repolish, set_pill_kind, toggle_row,
)

logger = logging.getLogger(__name__)

_SHADOW = 26   # 窗口四周投影留白
_TABS = [
    ("basic",   "基础",   "sliders"),
    ("hotkey",  "快捷键", "key"),
    ("hotword", "热词",   "tag"),
    ("history", "历史",   "clock"),
    ("log",     "日志",   "log"),
]


class _DragFilter(QObject):
    """标题栏按住拖动（startSystemMove，X11/Wayland 通吃）。"""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._win = window

    def eventFilter(self, _obj, ev) -> bool:  # noqa: N802
        if ev.type() == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton:
            handle = self._win.windowHandle()
            if handle is not None:
                handle.startSystemMove()
            return True
        return False


class _HistRow(QFrame):
    """历史行：mono 元信息 + 正文，单击复制。"""

    def __init__(self, meta: str, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("vi", "histRow")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("单击复制到剪贴板")
        self._text = text
        lay = QVBoxLayout(self)
        lay.setContentsMargins(11, 8, 11, 8)
        lay.setSpacing(3)
        self._meta = QLabel(meta)
        self._meta.setProperty("vi", "histMeta")
        body = QLabel(text)
        body.setProperty("vi", "histText")
        body.setWordWrap(True)
        lay.addWidget(self._meta)
        lay.addWidget(body)
        self._meta_text = meta

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            QGuiApplication.clipboard().setText(self._text)
            self._meta.setText("✓ 已复制")
            QTimer.singleShot(900, lambda: self._meta.setText(self._meta_text))
        e.accept()


class SettingsWindow(QDialog):
    """设置窗口（不阻塞主程序）"""

    configChanged = Signal(Config)
    autostartToggled = Signal(bool)
    reloadModelRequested = Signal()
    hudResetRequested = Signal()   # 录音浮窗「恢复默认位置」

    def __init__(self, config: Config, history: History, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Voice Input 设置")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(720 + _SHADOW * 2, 680 + _SHADOW * 2)
        self.config = config
        self.history = history
        self.recorder_for_levels: Recorder | None = None

        # ---- 外壳 + 投影 ----
        root = QVBoxLayout(self)
        root.setContentsMargins(_SHADOW, _SHADOW, _SHADOW, _SHADOW)
        self.shell = QFrame()
        self.shell.setObjectName("shell")
        root.addWidget(self.shell)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(44)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(24, 33, 56, 80))
        self.shell.setGraphicsEffect(shadow)

        col = QVBoxLayout(self.shell)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._build_titlebar())
        col.addWidget(self._build_topnav())

        # ---- 页面堆叠 ----
        self.pages = QStackedWidget()
        self._page_keys: list[str] = []
        for key, builder in (
            ("basic", self._build_basic_page),
            ("hotkey", self._build_hotkey_page),
            ("hotword", self._build_hotwords_page),
            ("history", self._build_history_page),
            ("log", self._build_log_page),
        ):
            self.pages.addWidget(self._wrap_scroll(builder()))
            self._page_keys.append(key)
        col.addWidget(self.pages, 1)
        col.addWidget(self._build_footer())

        apply_soft_theme(self)
        self._refresh_titlebar_icons()
        self._on_preset_changed()

        # 日志刷新定时器
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._log_timer.start(1500)

    # ================= 外壳区域 =================
    def _build_titlebar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("titlebar")
        bar.setFixedHeight(52)
        bar.installEventFilter(_DragFilter(self))
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 0, 12, 0)
        lay.setSpacing(9)

        self._brand = IconBadge("mic", size=26, icon_size=15, radius=8)
        lay.addWidget(self._brand)
        title = QLabel("Voice Input")
        title.setObjectName("winTitle")
        lay.addWidget(title)
        lay.addStretch(1)

        # ☀/☾ 主题切换
        toggle = QFrame()
        toggle.setObjectName("themeToggle")
        tl = QHBoxLayout(toggle)
        tl.setContentsMargins(3, 3, 3, 3)
        tl.setSpacing(2)
        self.btn_light = QPushButton()
        self.btn_dark = QPushButton()
        for btn, name in ((self.btn_light, "light"), (self.btn_dark, "dark")):
            btn.setProperty("themeBtn", "true")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip("浅色" if name == "light" else "深色")
            btn.clicked.connect(lambda _=False, n=name: self._switch_theme(n))
            tl.addWidget(btn)
        lay.addWidget(toggle)

        # 最小化 / 关闭
        self.btn_min = QPushButton()
        self.btn_min.setProperty("winBtn", "true")
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_winclose = QPushButton()
        self.btn_winclose.setObjectName("winClose")
        self.btn_winclose.setProperty("winBtn", "true")
        self.btn_winclose.setCursor(Qt.PointingHandCursor)
        self.btn_winclose.clicked.connect(self.hide)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_winclose)
        return bar

    def _build_topnav(self) -> QFrame:
        nav = QFrame()
        nav.setObjectName("topnav")
        lay = QHBoxLayout(nav)
        lay.setContentsMargins(16, 14, 16, 14)
        self.seg_tabs = SegmentedControl(_TABS)
        self.seg_tabs.changed.connect(self._on_tab_changed)
        lay.addStretch(1)
        lay.addWidget(self.seg_tabs)
        lay.addStretch(1)
        return nav

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("footer")
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(24, 13, 10, 13)
        lay.setSpacing(10)
        lay.addStretch(1)
        self.btn_close = QPushButton("关闭")
        self.btn_close.setProperty("ghost", "true")
        self.btn_close.clicked.connect(self.hide)
        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("primary")
        self.btn_save.clicked.connect(self._save)
        lay.addWidget(self.btn_close)
        lay.addWidget(self.btn_save)
        grip = QSizeGrip(footer)
        grip.setFixedSize(14, 14)
        lay.addWidget(grip, 0, Qt.AlignBottom)
        return footer

    def _wrap_scroll(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _page_canvas(self) -> tuple[QWidget, QVBoxLayout]:
        canvas = QWidget()
        canvas.setObjectName("pageCanvas")
        lay = QVBoxLayout(canvas)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(14)
        return canvas, lay

    # ================= 小工具 =================
    def _field(self, label: str, w: QWidget, hint: str = "") -> QVBoxLayout:
        """设计稿 field：label 在上，控件通栏，可选 hint。"""
        box = QVBoxLayout()
        box.setSpacing(8)
        box.addWidget(field_label(label))
        box.addWidget(w)
        if hint:
            box.addWidget(hint_label(hint))
        return box

    def _two_col(self, left: QVBoxLayout, right: QVBoxLayout) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(18)
        for part in (left, right):
            cell = QWidget()
            cell.setLayout(part)
            row.addWidget(cell, 1)
        return row

    def _wrap_layout(self, layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    # ================= 基础页 =================
    def _build_basic_page(self) -> QWidget:
        canvas, col = self._page_canvas()

        # ===== 卡片 1：识别模型 =====
        card = Card("mic", "识别模型", "选择推理引擎与运行设备")

        self.cmb_preset = QComboBox()
        for key, p in PRESETS.items():
            self.cmb_preset.addItem(p.label, key)
        cur = get_preset(self.config.model_preset)
        for i in range(self.cmb_preset.count()):
            if self.cmb_preset.itemData(i) == cur.key:
                self.cmb_preset.setCurrentIndex(i)
                break
        self.cmb_preset.currentIndexChanged.connect(self._on_preset_changed)
        card.add(self._field("模型预设", self.cmb_preset))

        # 💡 描述 + 下载状态 pill
        desc_row = QHBoxLayout()
        desc_row.setSpacing(10)
        self.lbl_preset_desc = hint_label("")
        desc_row.addWidget(self.lbl_preset_desc, 1)
        self.pill_download = pill_label("", "pillOk")
        desc_row.addWidget(self.pill_download, 0, Qt.AlignVCenter)
        card.add(desc_row)

        # 自定义模型路径（仅 custom 预设可见）
        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        self.txt_custom_path = QLineEdit(self.config.custom_model_path)
        self.txt_custom_path.setPlaceholderText("ModelScope 模型 ID（如 iic/xxx）或 本地模型目录绝对路径")
        self.txt_custom_path.textChanged.connect(self._on_preset_changed)
        btn_browse = QPushButton("浏览…")
        btn_browse.clicked.connect(self._browse_model_dir)
        custom_row.addWidget(self.txt_custom_path, 1)
        custom_row.addWidget(btn_browse)
        self.custom_path_widget = self._wrap_layout(custom_row)
        card.add(self.custom_path_widget)

        self.lbl_model_path = hint_label("", mono=True)
        self.lbl_model_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card.add(self.lbl_model_path)

        self.lbl_model_help = hint_label(
            "📥 默认模型自动下载到 ~/.cache/modelscope/hub/models/ ；"
            "想用其它模型：到 modelscope.cn 或 huggingface.co 下载 FunASR 兼容模型，"
            "选「📁 自定义模型」填模型 ID（自动下载）或本地目录路径。"
        )
        card.add(self.lbl_model_help)

        card.divider()

        # 两列：模型设备（分段） | 识别语言
        self.seg_device = SegmentedControl(
            [("cuda:0", "cuda:0", None), ("cpu", "cpu", None)], full=True)
        self.seg_device.set_value(self.config.model_device)
        left = self._field("模型设备", self.seg_device)

        self.cmb_lang = QComboBox()
        for lang in ["zh", "en", "auto", "yue", "ja", "ko"]:
            self.cmb_lang.addItem(lang)
        self.cmb_lang.setCurrentText(self.config.language)
        right = self._field("识别语言", self.cmb_lang)
        self.lbl_lang_na = hint_label("该模型不支持切换")
        self.lbl_lang_na.hide()
        right.addWidget(self.lbl_lang_na)
        card.add(self._two_col(left, right))
        col.addWidget(card)

        # ===== 卡片 2：音频输入 =====
        card2 = Card("wave", "音频输入", "麦克风与文字注入方式")

        self.cmb_mic = QComboBox()
        self.cmb_mic.addItem("系统默认", None)
        try:
            for d in Recorder().list_devices():
                label = f"[{d['index']}] {d['name']}" + ("  ★默认" if d['is_default'] else "")
                self.cmb_mic.addItem(label, d['index'])
            target_idx = self.config.input_device_index
            for i in range(self.cmb_mic.count()):
                if self.cmb_mic.itemData(i) == target_idx:
                    self.cmb_mic.setCurrentIndex(i)
                    break
        except Exception as e:
            logger.warning("list mic devices failed: %s", e)
        card2.add(self._field("麦克风", self.cmb_mic))

        # 电平条 + 测试按钮（设计稿 MicTest）
        self.volume_meter = BarMeter()
        self.btn_test_mic = QPushButton("测试 5 秒")
        self.btn_test_mic.setObjectName("primary")
        self.btn_test_mic.setMinimumWidth(110)
        self.btn_test_mic.clicked.connect(self._test_mic)
        mic_row = QHBoxLayout()
        mic_row.setSpacing(14)
        mic_row.addWidget(self.volume_meter, 1)
        mic_row.addWidget(self.btn_test_mic)
        card2.add(mic_row)

        card2.divider()

        self.seg_input = SegmentedControl(
            [("paste", "粘贴（推荐）", None), ("type", "模拟键入", None)])
        self.seg_input.set_value(self.config.input_method
                                 if self.config.input_method in ("paste", "type") else "paste")
        card2.add(self._field("输入方式", self.seg_input,
                              hint="paste 对中文最稳；type 走 xdotool，可能丢字"))
        col.addWidget(card2)

        # ===== 卡片 3：提示与启动 =====
        card3 = Card("check", "提示与启动", "提示音、录音浮窗与开机自启")

        self.chk_sound = ToggleSwitch()
        self.chk_sound.setChecked(self.config.play_sound)
        card3.add(toggle_row("录音提示音", "开始 / 结束播放 ding 声", self.chk_sound))

        # 音量滑杆（开关打开才显示）
        vol_row = QHBoxLayout()
        vol_row.setSpacing(14)
        lbl_vol = hint_label("提示音量")
        lbl_vol.setFixedWidth(64)
        self.sld_volume = QSlider(Qt.Horizontal)
        self.sld_volume.setRange(0, 100)
        self.sld_volume.setValue(round(self.config.sound_volume * 100))
        self.lbl_vol_pct = hint_label(f"{self.sld_volume.value()}%", mono=True)
        self.lbl_vol_pct.setFixedWidth(38)
        self.lbl_vol_pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sld_volume.valueChanged.connect(
            lambda v: self.lbl_vol_pct.setText(f"{v}%"))
        vol_row.addWidget(lbl_vol)
        vol_row.addWidget(self.sld_volume, 1)
        vol_row.addWidget(self.lbl_vol_pct)
        self.vol_row_widget = self._wrap_layout(vol_row)
        self.vol_row_widget.setVisible(self.config.play_sound)
        self.chk_sound.toggled.connect(self.vol_row_widget.setVisible)
        card3.add(self.vol_row_widget)

        card3.divider()

        self.chk_hud = ToggleSwitch()
        self.chk_hud.setChecked(self.config.show_hud)
        card3.add(toggle_row("录音浮窗", "可按住拖到任意位置（自动记忆）；默认屏幕底部居中弹出",
                             self.chk_hud))

        # 恢复默认位置（开关打开才显示）
        hud_row = QHBoxLayout()
        hud_row.setSpacing(14)
        btn_hud_reset = QPushButton("恢复默认位置")
        btn_hud_reset.setProperty("ghost", True)
        btn_hud_reset.setCursor(Qt.PointingHandCursor)
        btn_hud_reset.clicked.connect(self.hudResetRequested.emit)
        hud_row.addWidget(btn_hud_reset)
        hud_row.addWidget(hint_label("浮窗拖丢了？点这里回到屏幕底部居中"), 1)
        self.hud_row_widget = self._wrap_layout(hud_row)
        self.hud_row_widget.setVisible(self.config.show_hud)
        self.chk_hud.toggled.connect(self.hud_row_widget.setVisible)
        card3.add(self.hud_row_widget)

        card3.divider()

        self.chk_autostart = ToggleSwitch()
        self.chk_autostart.setChecked(self.config.autostart_enabled)
        card3.add(toggle_row("开机自启", "登录后自动在后台启动", self.chk_autostart))
        col.addWidget(card3)

        col.addStretch(1)
        return canvas

    def _on_preset_changed(self) -> None:
        """模型预设变化：更新说明、本地路径、自定义行显隐、语言/热词可用性。"""
        p = get_preset(self.cmb_preset.currentData())
        self.lbl_preset_desc.setText("💡 " + p.desc)
        is_custom = p.key == "custom"
        if hasattr(self, "custom_path_widget"):
            self.custom_path_widget.setVisible(is_custom)
        if is_custom:
            cur = self.txt_custom_path.text().strip()
            self.lbl_model_path.setText(cur if cur else "（请在上方填 模型 ID 或本地目录）")
            self.pill_download.hide()
        else:
            path = model_cache_path(p)
            self.lbl_model_path.setText(str(path))
            if path.exists():
                self.pill_download.setText("✓ 已下载")
                set_pill_kind(self.pill_download, "pillOk")
            else:
                self.pill_download.setText("首次选用自动下载 · 约 1GB")
                set_pill_kind(self.pill_download, "pillWarn")
            self.pill_download.show()
        self.cmb_lang.setEnabled(p.accepts_language)
        if hasattr(self, "lbl_lang_na"):
            self.lbl_lang_na.setVisible(not p.accepts_language)

        # 热词页动态 pill
        if hasattr(self, "pill_hotword"):
            if p.accepts_hotword:
                self.pill_hotword.setText(f"✓ 当前模型「{p.label}」热词增强强")
                set_pill_kind(self.pill_hotword, "pillOk")
            else:
                self.pill_hotword.setText(
                    f"当前模型「{p.label}」热词支持较弱 · 想用热词请切到 Paraformer 中文")
                set_pill_kind(self.pill_hotword, "pillWarn")

    def _browse_model_dir(self) -> None:
        """选本地模型目录，并自动切到「自定义模型」。"""
        d = QFileDialog.getExistingDirectory(self, "选择模型目录")
        if not d:
            return
        self.txt_custom_path.setText(d)
        for i in range(self.cmb_preset.count()):
            if self.cmb_preset.itemData(i) == "custom":
                self.cmb_preset.setCurrentIndex(i)
                break

    def _test_mic(self) -> None:
        """录 5 秒看音量条"""
        if self.recorder_for_levels is not None:
            return
        idx = self.cmb_mic.currentData()
        self.recorder_for_levels = Recorder(
            sample_rate=16000,
            input_device=idx,
            on_level=self.volume_meter.set_level,
        )
        if not self.recorder_for_levels.start():
            QMessageBox.warning(self, "录音失败", "无法打开麦克风，请检查设备和权限。")
            self.recorder_for_levels = None
            return
        self.btn_test_mic.setEnabled(False)
        self.btn_test_mic.setText("● 录音中…")
        QTimer.singleShot(5000, self._stop_test_mic)

    def _stop_test_mic(self) -> None:
        if self.recorder_for_levels is None:
            return
        self.recorder_for_levels.stop()
        self.recorder_for_levels = None
        self.volume_meter.set_level(0)
        self.btn_test_mic.setEnabled(True)
        self.btn_test_mic.setText("测试 5 秒")

    # ================= 快捷键页 =================
    def _build_hotkey_page(self) -> QWidget:
        canvas, col = self._page_canvas()

        card = Card("key", "说话快捷键", "按住说话，松开识别并粘贴")
        row = QHBoxLayout()
        row.setSpacing(14)
        self.lbl_keycap = QLabel(self.config.hotkey.upper())
        self.lbl_keycap.setProperty("vi", "keycapBig")
        row.addWidget(self.lbl_keycap, 0, Qt.AlignVCenter)
        self.hotkey_btn = HotkeyCaptureButton(self.config.hotkey)
        self.hotkey_btn.captured.connect(
            lambda spec: self.lbl_keycap.setText(spec.upper()))
        row.addWidget(self.hotkey_btn, 0, Qt.AlignVCenter)
        row.addWidget(hint_label("推荐 F4 / F9 / 右 Ctrl 等不常用键；被系统占用的键会被拦截"), 1)
        card.add(row)
        col.addWidget(card)

        card2 = Card("cpu", "粘贴快捷键（高级）")
        self.cmb_paste = QComboBox()
        self.cmb_paste.setEditable(True)
        self.cmb_paste.addItems(["ctrl+v", "shift+Insert"])
        self.cmb_paste.setCurrentText(self.config.paste_key)
        self.cmb_term_paste = QComboBox()
        self.cmb_term_paste.setEditable(True)
        self.cmb_term_paste.addItems(["ctrl+shift+v", "shift+Insert", "ctrl+Insert"])
        self.cmb_term_paste.setCurrentText(self.config.terminal_paste_key)
        card2.add(self._two_col(
            self._field("普通应用", self.cmb_paste),
            self._field("终端窗口", self.cmb_term_paste),
        ))
        col.addWidget(card2)

        col.addStretch(1)
        return canvas

    # ================= 热词页 =================
    def _build_hotwords_page(self) -> QWidget:
        canvas, col = self._page_canvas()

        card = Card("tag", "热词增强", "让识别更倾向这些专有名词")
        pill_row = QHBoxLayout()
        self.pill_hotword = pill_label("", "pillOk")
        pill_row.addWidget(self.pill_hotword, 0, Qt.AlignLeft)
        pill_row.addStretch(1)
        card.add(pill_row)

        self.chips_hotwords = ChipFlow(self.config.hotwords.split())
        card.add(self.chips_hotwords)
        card.add(hint_label("空格分隔可批量添加 · 建议 < 50 个 · 中文请从别处复制后 Ctrl+V 粘贴"))
        col.addWidget(card)

        col.addStretch(1)
        return canvas

    # ================= 历史页 =================
    def _build_history_page(self) -> QWidget:
        canvas, col = self._page_canvas()

        corner = QWidget()
        cl = QHBoxLayout(corner)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)
        btn_refresh = QPushButton("刷新")
        btn_refresh.setProperty("ghost", "true")
        btn_refresh.clicked.connect(self.refresh_history)
        btn_clear = QPushButton("清空")
        btn_clear.setProperty("ghost", "true")
        btn_clear.clicked.connect(self._clear_history)
        cl.addWidget(btn_refresh)
        cl.addWidget(btn_clear)

        card = Card("clock", "识别历史", "单击任意一条复制到剪贴板", corner=corner)
        self._hist_box = QVBoxLayout()
        self._hist_box.setSpacing(4)
        card.add(self._hist_box)
        self._lbl_hist_empty = hint_label("还没有识别记录，按住快捷键说一句试试～")
        self._hist_box.addWidget(self._lbl_hist_empty)
        col.addWidget(card)

        col.addStretch(1)
        self.refresh_history()
        return canvas

    def refresh_history(self) -> None:
        # 清掉旧行（保留空态提示）
        while self._hist_box.count():
            item = self._hist_box.takeAt(0)
            w = item.widget()
            if w is not None and w is not self._lbl_hist_empty:
                w.setParent(None)   # 立刻移出视图，避免 deleteLater 前的幽灵重影
                w.deleteLater()
        items = list(reversed(self.history.recent()))
        self._lbl_hist_empty.setVisible(not items)
        self._hist_box.addWidget(self._lbl_hist_empty)
        for it in items:
            ts = datetime.fromtimestamp(it.ts).strftime("%H:%M:%S")
            meta = f"{ts} · {it.duration:.1f}s · RTF {it.rtf:.2f} · {it.language}"
            self._hist_box.addWidget(_HistRow(meta, it.text))

    def _clear_history(self) -> None:
        if QMessageBox.question(self, "清空历史", "确定清空所有识别历史？") == QMessageBox.Yes:
            self.history.clear()
            self.refresh_history()

    # ================= 日志页 =================
    def _build_log_page(self) -> QWidget:
        canvas, col = self._page_canvas()
        card = Card("log", "运行日志", "实时显示最后 200 行")
        card.add(hint_label(f"日志文件: {LOG_DIR / 'voice-input.log'}", mono=True))
        self.txt_log = QTextEdit()
        self.txt_log.setProperty("vi", "log")
        self.txt_log.setReadOnly(True)
        self.txt_log.setLineWrapMode(QTextEdit.NoWrap)
        self.txt_log.setMinimumHeight(380)
        card.add(self.txt_log)
        col.addWidget(card, 1)
        return canvas

    def _refresh_log(self) -> None:
        if self._page_keys[self.pages.currentIndex()] != "log":
            return
        log_file = LOG_DIR / "voice-input.log"
        if not log_file.exists():
            return
        try:
            text = log_file.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()[-200:]
            self.txt_log.setPlainText("\n".join(lines))
            sb = self.txt_log.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception:
            pass

    # ================= Tab / 主题 =================
    def _on_tab_changed(self, key: str) -> None:
        self.pages.setCurrentIndex(self._page_keys.index(key))
        if key == "log":
            self._refresh_log()

    def _switch_theme(self, name: str) -> None:
        if name == current_theme():
            return
        set_theme(name)
        self._retheme()

    def _retheme(self) -> None:
        """主题切换后：重套 QSS + 刷新自绘控件与图标。"""
        apply_soft_theme(self)
        self._refresh_titlebar_icons()
        self.seg_tabs.refresh_theme()
        self.seg_device.refresh_theme()
        self.seg_input.refresh_theme()
        # chips 的 × 图标颜色依赖主题，重建一遍
        self.chips_hotwords.set_words(self.chips_hotwords.words())
        # 自绘控件统一重绘
        for w in self.findChildren(QWidget):
            w.update()

    def _refresh_titlebar_icons(self) -> None:
        P = palette()
        is_dark = current_theme() == "dark"
        self.btn_light.setProperty("on", "false" if is_dark else "true")
        self.btn_dark.setProperty("on", "true" if is_dark else "false")
        self.btn_light.setIcon(line_icons.line_qicon(
            "sun", 14, P["accent"] if not is_dark else P["text_3"]))
        self.btn_dark.setIcon(line_icons.line_qicon(
            "moon", 14, P["accent"] if is_dark else P["text_3"]))
        self.btn_min.setIcon(line_icons.line_qicon("minus", 13, P["text_2"]))
        self.btn_winclose.setIcon(line_icons.line_qicon("x", 12, P["text_2"]))
        for b in (self.btn_light, self.btn_dark):
            repolish(b)

    # ================= 保存 =================
    def _save(self) -> None:
        cfg = self.config
        cfg.model_preset = self.cmb_preset.currentData()
        cfg.custom_model_path = self.txt_custom_path.text().strip()
        cfg.model_device = self.seg_device.value()
        cfg.language = self.cmb_lang.currentText()
        cfg.input_method = self.seg_input.value()
        cfg.input_device_index = self.cmb_mic.currentData()
        cfg.play_sound = self.chk_sound.isChecked()
        cfg.sound_volume = self.sld_volume.value() / 100.0
        cfg.show_hud = self.chk_hud.isChecked()
        autostart_new = self.chk_autostart.isChecked()
        cfg.autostart_enabled = autostart_new

        cfg.hotkey = self.hotkey_btn.spec()
        cfg.paste_key = self.cmb_paste.currentText().strip() or "ctrl+v"
        cfg.terminal_paste_key = self.cmb_term_paste.currentText().strip() or "ctrl+shift+v"

        cfg.hotwords = " ".join(self.chips_hotwords.words())

        cfg.save()
        logger.info("config saved from UI")
        self.configChanged.emit(cfg)
        self.autostartToggled.emit(autostart_new)
        QMessageBox.information(self, "已保存", "设置已保存。\n模型设备/麦克风变更需重启程序。")
