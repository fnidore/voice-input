"""设置窗口：基础 / 快捷键 / 热词 / 历史 / 日志

清新简约「柔和卡片」版：顶部居中分段 Tab + 分组卡片 + 浅色蓝点缀。
业务逻辑与旧版保持一致，仅重组「基础」Tab 的视觉结构并改用 ToggleSwitch。
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.audio import Recorder
from core.config import Config, LOG_DIR
from core.history import History
from core.presets import PRESETS, get_preset, model_cache_path

from .hotkey_capture import HotkeyCaptureButton
from .style import PALETTE, apply_soft_theme
from .volume_meter import VolumeMeter
from .widgets import HSep, ToggleSwitch

logger = logging.getLogger(__name__)


class SettingsWindow(QDialog):
    """设置窗口（不阻塞主程序）"""

    configChanged = Signal(Config)
    autostartToggled = Signal(bool)
    reloadModelRequested = Signal()

    def __init__(self, config: Config, history: History, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Voice Input 设置")
        self.resize(680, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint)
        self.config = config
        self.history = history
        self.recorder_for_levels: Recorder | None = None

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_basic_tab(), "基础")
        self.tabs.addTab(self._build_hotkey_tab(), "快捷键")
        self.tabs.addTab(self._build_hotwords_tab(), "热词")
        self.tabs.addTab(self._build_history_tab(), "历史")
        self.tabs.addTab(self._build_log_tab(), "日志")

        # 底部按钮
        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("primary")   # 主按钮（蓝）
        self.btn_save.clicked.connect(self._save)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.hide)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_close)
        btn_row.addWidget(self.btn_save)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 10, 18, 16)
        root.setSpacing(8)
        root.addWidget(self.tabs)
        root.addLayout(btn_row)

        # 浅色「柔和卡片」主题
        apply_soft_theme(self)
        # 初始化模型说明/路径/语言灰显
        self._on_preset_changed()

        # 启动日志刷新定时器
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._log_timer.start(1500)

    # ---------- 小工具：构造一张卡片（QGroupBox + QFormLayout）----------
    def _card(self, title: str) -> tuple[QGroupBox, QFormLayout]:
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setSpacing(14)
        form.setContentsMargins(4, 6, 4, 2)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        return box, form

    # ---------- 基础 tab ----------
    def _build_basic_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(4, 6, 8, 6)
        col.setSpacing(16)

        # ===== 卡片 1：识别模型 =====
        card_model, form = self._card("识别模型")
        self._model_form = form

        self.cmb_preset = QComboBox()
        for key, p in PRESETS.items():
            self.cmb_preset.addItem(p.label, key)
        cur = get_preset(self.config.model_preset)
        for i in range(self.cmb_preset.count()):
            if self.cmb_preset.itemData(i) == cur.key:
                self.cmb_preset.setCurrentIndex(i)
                break
        self.cmb_preset.currentIndexChanged.connect(self._on_preset_changed)
        form.addRow("模型预设:", self.cmb_preset)

        self.lbl_preset_desc = QLabel()
        self.lbl_preset_desc.setWordWrap(True)
        self.lbl_preset_desc.setStyleSheet(f"color:{PALETTE['accent']}; font-size:12px;")
        form.addRow("", self.lbl_preset_desc)

        self.lbl_model_path = QLabel()
        self.lbl_model_path.setWordWrap(True)
        self.lbl_model_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_model_path.setStyleSheet(f"color:{PALETTE['text_3']}; font-size:11px;")
        form.addRow("模型路径:", self.lbl_model_path)

        self.txt_custom_path = QLineEdit(self.config.custom_model_path)
        self.txt_custom_path.setPlaceholderText("ModelScope 模型 ID（如 iic/xxx）或 本地模型目录绝对路径")
        self.txt_custom_path.textChanged.connect(self._on_preset_changed)
        btn_browse = QPushButton("浏览…")
        btn_browse.clicked.connect(self._browse_model_dir)
        custom_row = QHBoxLayout()
        custom_row.addWidget(self.txt_custom_path, 1)
        custom_row.addWidget(btn_browse)
        self.custom_path_widget = self._wrap_layout(custom_row)
        form.addRow("自定义模型:", self.custom_path_widget)

        self.lbl_model_help = QLabel(
            "📥 默认模型自动下载到 <b>~/.cache/modelscope/hub/models/</b><br>"
            "想用其它模型：到 <b>modelscope.cn</b> 或 <b>huggingface.co</b> 下载 FunASR 兼容模型，"
            "选「📁 自定义模型」填<b>模型 ID</b>（自动下载）或<b>本地目录路径</b>。"
        )
        self.lbl_model_help.setWordWrap(True)
        self.lbl_model_help.setOpenExternalLinks(True)
        self.lbl_model_help.setStyleSheet("color:#99a0b0; font-size:11px;")
        form.addRow("", self.lbl_model_help)

        form.addRow(HSep())

        self.cmb_device = QComboBox()
        self.cmb_device.addItems(["cuda:0", "cpu"])
        self.cmb_device.setCurrentText(self.config.model_device)
        form.addRow("模型设备:", self.cmb_device)

        self.cmb_lang = QComboBox()
        for lang in ["zh", "en", "auto", "yue", "ja", "ko"]:
            self.cmb_lang.addItem(lang)
        self.cmb_lang.setCurrentText(self.config.language)
        form.addRow("识别语言:", self.cmb_lang)
        col.addWidget(card_model)

        # ===== 卡片 2：音频输入 =====
        card_audio, form2 = self._card("音频输入")

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
        form2.addRow("麦克风:", self.cmb_mic)

        self.volume_meter = VolumeMeter()
        self.btn_test_mic = QPushButton("测试 5 秒")
        self.btn_test_mic.clicked.connect(self._test_mic)
        mic_row = QHBoxLayout()
        mic_row.addWidget(self.volume_meter, 1)
        mic_row.addWidget(self.btn_test_mic)
        form2.addRow("麦克风电平:", self._wrap_layout(mic_row))

        form2.addRow(HSep())

        self.cmb_input_method = QComboBox()
        self.cmb_input_method.addItems(["paste（推荐，中文最稳）", "type（xdotool，可能丢字）"])
        self.cmb_input_method.setCurrentIndex(0 if self.config.input_method == "paste" else 1)
        form2.addRow("输入方式:", self.cmb_input_method)
        col.addWidget(card_audio)

        # ===== 卡片 3：提示音与启动 =====
        card_misc, form3 = self._card("提示音与启动")

        self.chk_sound = ToggleSwitch()
        self.chk_sound.setChecked(self.config.play_sound)
        form3.addRow("录音提示音:", self.chk_sound)

        self.spn_volume = QDoubleSpinBox()
        self.spn_volume.setRange(0.0, 1.0)
        self.spn_volume.setSingleStep(0.1)
        self.spn_volume.setValue(self.config.sound_volume)
        form3.addRow("提示音量:", self.spn_volume)

        form3.addRow(HSep())

        self.chk_autostart = ToggleSwitch()
        self.chk_autostart.setChecked(self.config.autostart_enabled)
        form3.addRow("开机自启:", self.chk_autostart)
        col.addWidget(card_misc)

        col.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _on_preset_changed(self) -> None:
        """模型预设变化：更新说明、本地路径、自定义行显隐、语言/热词可用性。"""
        p = get_preset(self.cmb_preset.currentData())
        self.lbl_preset_desc.setText("💡 " + p.desc)
        is_custom = p.key == "custom"
        if hasattr(self, "custom_path_widget"):
            self._model_form.setRowVisible(self.custom_path_widget, is_custom)
        if is_custom:
            cur = self.txt_custom_path.text().strip()
            self.lbl_model_path.setText(cur if cur else "（请在上方填 模型 ID 或本地目录）")
        else:
            path = model_cache_path(p)
            mark = "✓ 已下载" if path.exists() else "· 首次选用会自动联网下载（约 1GB）"
            self.lbl_model_path.setText(f"{path}\n{mark}")
        self.cmb_lang.setEnabled(p.accepts_language)

        # 热词 tab 动态提示（在 _on_preset_changed 里更新，p 一定存在）
        if hasattr(self, "lbl_hotword_note"):
            if p.accepts_hotword:
                self.lbl_hotword_note.setText(
                    f"✅ 当前模型「{p.label}」热词增强强，下面的热词会显著提升识别准确率。"
                )
            else:
                self.lbl_hotword_note.setText(
                    f"⚠️ 当前模型「{p.label}」对热词支持弱，可能不明显生效；"
                    "想用热词请切到「Paraformer 中文」。"
                )

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

    def _wrap_layout(self, layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

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
        self.btn_test_mic.setText("录音中…")
        QTimer.singleShot(5000, self._stop_test_mic)

    def _stop_test_mic(self) -> None:
        if self.recorder_for_levels is None:
            return
        self.recorder_for_levels.stop()
        self.recorder_for_levels = None
        self.volume_meter.set_level(0)
        self.btn_test_mic.setEnabled(True)
        self.btn_test_mic.setText("测试 5 秒")

    # ---------- 快捷键 tab ----------
    def _build_hotkey_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 10, 8, 6)
        v.setSpacing(16)

        gb = QGroupBox("说话快捷键")
        gb_l = QVBoxLayout(gb)
        gb_l.setContentsMargins(4, 8, 4, 4)
        hint = QLabel(
            "按住设定的键说话，松开识别并粘贴。"
            "推荐使用 F4 / F9 / 右 Ctrl / 右 Alt 等不常用键；"
            "若系统已占用某个键，会被拦截。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#5a6071; font-size:12px;")
        gb_l.addWidget(hint)
        self.hotkey_btn = HotkeyCaptureButton(self.config.hotkey)
        gb_l.addWidget(self.hotkey_btn)
        v.addWidget(gb)

        gb2 = QGroupBox("粘贴快捷键（高级）")
        form = QFormLayout(gb2)
        form.setSpacing(14)
        form.setContentsMargins(4, 8, 4, 4)
        self.cmb_paste = QComboBox()
        self.cmb_paste.setEditable(True)
        self.cmb_paste.addItems(["ctrl+v", "shift+Insert"])
        self.cmb_paste.setCurrentText(self.config.paste_key)
        form.addRow("普通应用:", self.cmb_paste)

        self.cmb_term_paste = QComboBox()
        self.cmb_term_paste.setEditable(True)
        self.cmb_term_paste.addItems(["ctrl+shift+v", "shift+Insert", "ctrl+Insert"])
        self.cmb_term_paste.setCurrentText(self.config.terminal_paste_key)
        form.addRow("终端窗口:", self.cmb_term_paste)
        v.addWidget(gb2)

        v.addStretch(1)
        return w

    # ---------- 热词 tab ----------
    def _build_hotwords_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(4, 10, 8, 6)
        gb = QGroupBox("热词增强")
        v = QVBoxLayout(gb)
        v.setContentsMargins(4, 8, 4, 4)
        v.setSpacing(12)
        hint = QLabel(
            "热词列表（空格分隔），让识别更倾向这些词。例如: 涛涛鱼 SenseVoice 机械臂 强化学习。"
            "热词过多会影响速度，建议 < 50 个。"
            "💡 中文热词请从别处复制后按 Ctrl+V 粘贴。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#5a6071; font-size:12px;")
        v.addWidget(hint)

        self.lbl_hotword_note = QLabel()
        self.lbl_hotword_note.setWordWrap(True)
        self.lbl_hotword_note.setStyleSheet(f"color:{PALETTE['accent']}; font-size:12px;")
        v.addWidget(self.lbl_hotword_note)

        self.txt_hotwords = QPlainTextEdit()
        self.txt_hotwords.setPlaceholderText("中文热词请从别处复制后 Ctrl+V 粘贴")
        self.txt_hotwords.setPlainText(self.config.hotwords)
        v.addWidget(self.txt_hotwords, 1)
        outer.addWidget(gb, 1)
        return w

    # ---------- 历史 tab ----------
    def _build_history_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 10, 8, 6)
        v.setSpacing(12)
        self.list_history = QListWidget()
        self.list_history.itemDoubleClicked.connect(self._copy_history_item)
        v.addWidget(self.list_history, 1)

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self.refresh_history)
        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self._clear_history)
        btn_row.addWidget(btn_refresh)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch(1)
        lbl = QLabel("双击复制到剪贴板")
        lbl.setStyleSheet("color:#99a0b0; font-size:12px;")
        btn_row.addWidget(lbl)
        v.addLayout(btn_row)
        self.refresh_history()
        return w

    def refresh_history(self) -> None:
        self.list_history.clear()
        for item in reversed(self.history.recent()):
            ts = datetime.fromtimestamp(item.ts).strftime("%H:%M:%S")
            label = f"[{ts}] ({item.duration:.1f}s, RTF={item.rtf:.2f}, {item.language})  {item.text}"
            li = QListWidgetItem(label)
            li.setData(Qt.UserRole, item.text)
            self.list_history.addItem(li)

    def _copy_history_item(self, item: QListWidgetItem) -> None:
        text = item.data(Qt.UserRole)
        QGuiApplication.clipboard().setText(text)

    def _clear_history(self) -> None:
        if QMessageBox.question(self, "清空历史", "确定清空所有识别历史？") == QMessageBox.Yes:
            self.history.clear()
            self.refresh_history()

    # ---------- 日志 tab ----------
    def _build_log_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 10, 8, 6)
        v.setSpacing(10)
        lbl = QLabel(f"日志文件: {LOG_DIR / 'voice-input.log'}")
        lbl.setStyleSheet("color:#99a0b0; font-size:11px;")
        v.addWidget(lbl)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setLineWrapMode(QTextEdit.NoWrap)
        v.addWidget(self.txt_log, 1)
        return w

    def _refresh_log(self) -> None:
        if self.tabs.currentIndex() != 4:
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

    # ---------- 保存 ----------
    def _save(self) -> None:
        cfg = self.config
        cfg.model_preset = self.cmb_preset.currentData()
        cfg.custom_model_path = self.txt_custom_path.text().strip()
        cfg.model_device = self.cmb_device.currentText()
        cfg.language = self.cmb_lang.currentText()
        cfg.input_method = "paste" if self.cmb_input_method.currentIndex() == 0 else "type"
        cfg.input_device_index = self.cmb_mic.currentData()
        cfg.play_sound = self.chk_sound.isChecked()
        cfg.sound_volume = self.spn_volume.value()
        autostart_new = self.chk_autostart.isChecked()
        cfg.autostart_enabled = autostart_new

        cfg.hotkey = self.hotkey_btn.spec()
        cfg.paste_key = self.cmb_paste.currentText().strip() or "ctrl+v"
        cfg.terminal_paste_key = self.cmb_term_paste.currentText().strip() or "ctrl+shift+v"

        cfg.hotwords = self.txt_hotwords.toPlainText().strip()

        cfg.save()
        logger.info("config saved from UI")
        self.configChanged.emit(cfg)
        self.autostartToggled.emit(autostart_new)
        QMessageBox.information(self, "已保存", "设置已保存。\n模型设备/麦克风变更需重启程序。")
