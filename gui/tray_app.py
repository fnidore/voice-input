"""托盘应用：状态机 + 串起 core 模块"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from enum import Enum

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from core import sound
from core.audio import Recorder
from core.config import Config
from core.history import History, HistoryItem
from core.hotkey import HotkeyListener
from core.inject import (
    check_deps,
    inject_via_paste,
    inject_via_type,
)
from core.recognizer import Recognizer

from .floating_window import ActivationReason, FloatingStatusWindow
from .icons import (
    icon_error,
    icon_idle,
    icon_paused,
    icon_processing,
    icon_recording,
)
from .settings_window import SettingsWindow

logger = logging.getLogger(__name__)


def _notify(title: str, body: str, critical: bool = False) -> None:
    """用 notify-send 发桌面通知，避免 QSystemTrayIcon.showMessage 触发 GNOME
    AppIndicator 把托盘图标 fallback 成蓝色信息感叹号。"""
    try:
        subprocess.Popen(
            [
                "notify-send",
                "-a", "Voice Input",
                "-u", "critical" if critical else "normal",
                "-i", "audio-input-microphone",
                title,
                body,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.debug("notify-send failed: %s", e)


class State(Enum):
    INIT = "init"
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    ERROR = "error"
    PAUSED = "paused"


class TrayApp(QObject):

    levelChanged = Signal(float)
    stateChanged = Signal(object)   # State
    recognized = Signal(object)     # HistoryItem

    def __init__(
        self,
        app: QApplication,
        config: Config,
        use_floating: bool = False,
    ) -> None:
        super().__init__()
        self.app = app
        self.config = config
        self.use_floating = use_floating
        self.history = History(max_items=config.history_max)
        self.recognizer = Recognizer(device=config.model_device)
        self.recorder: Recorder | None = None
        self.hotkey = HotkeyListener(
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )
        self.state = State.INIT

        # 根据托盘可用性选择 UI backend（两者接口一致）
        if use_floating:
            logger.info("UI backend = FloatingStatusWindow (no system tray)")
            self.tray = FloatingStatusWindow()
        else:
            logger.info("UI backend = QSystemTrayIcon")
            self.tray = QSystemTrayIcon(icon_idle())

        self.tray.setIcon(icon_idle())
        self.tray.setToolTip("Voice Input · 初始化中...")
        self.menu = QMenu()
        self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray_activated)

        self.settings_window: SettingsWindow | None = None
        self.recognized.connect(self._on_recognized)
        self.stateChanged.connect(self._on_state_changed)

    # ---------- 启动 ----------
    def start(self) -> None:
        missing = check_deps(self.config.input_method)
        if missing:
            QMessageBox.critical(
                None,
                "缺少系统依赖",
                f"缺少: {', '.join(missing)}\n请先运行: sudo apt install -y {' '.join(missing)}",
            )
            self.app.quit()
            return
        self.tray.show()
        # 模型加载放后台
        threading.Thread(target=self._load_model_async, daemon=True).start()

    def _load_model_async(self) -> None:
        self._set_state(State.INIT)
        self.tray.setToolTip("Voice Input · 加载模型中...")
        try:
            self.recognizer.load()
        except Exception as e:
            logger.exception("model load failed")
            self._set_state(State.ERROR)
            self.tray.setToolTip(f"Voice Input · 模型加载失败: {e}")
            # 用 notify-send 而不是 tray.showMessage（避免 GNOME AppIndicator
            # 把托盘图标替换成蓝色感叹号 fallback）
            _notify("模型加载失败", str(e), critical=True)
            return
        self.hotkey.set_hotkey(self.config.hotkey)
        self.hotkey.start()
        self._set_state(State.IDLE)
        self.tray.setToolTip(
            f"Voice Input · 待机（按住 {self.hotkey.description} 说话）"
        )
        _notify(
            "Voice Input 就绪",
            f"按住 [{self.hotkey.description}] 说话",
        )

    # ---------- 菜单 ----------
    def _build_menu(self) -> None:
        self.act_state = QAction("状态: 初始化中", self.menu)
        self.act_state.setEnabled(False)
        self.menu.addAction(self.act_state)
        self.menu.addSeparator()

        self.act_pause = QAction("暂停监听", self.menu)
        self.act_pause.setCheckable(True)
        self.act_pause.triggered.connect(self._toggle_pause)
        self.menu.addAction(self.act_pause)

        act_settings = QAction("设置...", self.menu)
        act_settings.triggered.connect(self.show_settings)
        self.menu.addAction(act_settings)

        act_reload = QAction("重新加载模型", self.menu)
        act_reload.triggered.connect(self._reload_model)
        self.menu.addAction(act_reload)

        self.menu.addSeparator()
        act_quit = QAction("退出", self.menu)
        act_quit.triggered.connect(self.quit)
        self.menu.addAction(act_quit)

    def _on_tray_activated(self, reason) -> None:
        # 兼容 QSystemTrayIcon.ActivationReason 和 FloatingStatusWindow 的 IntEnum
        double_click_values = (
            int(QSystemTrayIcon.DoubleClick),
            int(ActivationReason.DoubleClick),
        )
        if int(reason) in double_click_values:
            self.show_settings()

    def show_settings(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.config, self.history)
            self.settings_window.configChanged.connect(self._apply_config)
            self.settings_window.autostartToggled.connect(self._toggle_autostart)
            self.recognized.connect(lambda _: self.settings_window.refresh_history())
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _toggle_pause(self, checked: bool) -> None:
        if checked:
            self.hotkey.stop()
            self._set_state(State.PAUSED)
            self.act_pause.setText("继续监听")
        else:
            self.hotkey.set_hotkey(self.config.hotkey)
            self.hotkey.start()
            self._set_state(State.IDLE)
            self.act_pause.setText("暂停监听")

    def _reload_model(self) -> None:
        if self.state == State.PROCESSING:
            QMessageBox.warning(None, "稍等", "正在识别，等一下再重载。")
            return
        self.recognizer = Recognizer(device=self.config.model_device)
        threading.Thread(target=self._load_model_async, daemon=True).start()

    def _toggle_autostart(self, enabled: bool) -> None:
        from .autostart import set_autostart  # 延迟 import
        try:
            set_autostart(enabled)
            _notify(
                "开机自启",
                "已启用（登录后自动启动）" if enabled else "已禁用",
            )
        except Exception as e:
            QMessageBox.critical(None, "自启配置失败", str(e))

    def _apply_config(self, cfg: Config) -> None:
        # 在线更新部分配置
        if cfg.hotkey != self.hotkey.description:
            self.hotkey.set_hotkey(cfg.hotkey)
        self.tray.setToolTip(
            f"Voice Input · 待机（按住 {self.hotkey.description} 说话）"
        )

    def quit(self) -> None:
        try:
            self.hotkey.stop()
        except Exception:
            pass
        if self.recorder is not None:
            try:
                self.recorder.stop()
            except Exception:
                pass
        self.app.quit()

    # ---------- 状态机 ----------
    def _set_state(self, s: State) -> None:
        self.state = s
        self.stateChanged.emit(s)

    def _on_state_changed(self, s: State) -> None:
        labels = {
            State.INIT: ("状态: 初始化中", icon_idle()),
            State.IDLE: ("状态: 待机", icon_idle()),
            State.RECORDING: ("状态: 录音中", icon_recording()),
            State.PROCESSING: ("状态: 识别中", icon_processing()),
            State.ERROR: ("状态: 错误", icon_error()),
            State.PAUSED: ("状态: 已暂停", icon_paused()),
        }
        text, ico = labels.get(s, ("状态: ?", icon_idle()))
        self.act_state.setText(text)
        self.tray.setIcon(ico)

    # ---------- 快捷键 -> 录音 ----------
    def _on_hotkey_press(self) -> None:
        if self.state not in (State.IDLE,):
            return
        self.recorder = Recorder(
            sample_rate=self.config.sample_rate,
            input_device=self.config.input_device_index,
            on_level=lambda v: self.levelChanged.emit(v),
        )
        if not self.recorder.start():
            logger.error("recorder failed to start")
            self.recorder = None
            self._set_state(State.ERROR)
            QTimer.singleShot(2000, lambda: self._set_state(State.IDLE))
            return
        self._set_state(State.RECORDING)
        if self.config.play_sound:
            sound.play_start(self.config.sound_volume)

    def _on_hotkey_release(self) -> None:
        if self.state != State.RECORDING:
            return
        if self.recorder is None:
            return
        audio = self.recorder.stop()
        self.recorder = None
        if self.config.play_sound:
            sound.play_stop(self.config.sound_volume)

        if audio is None or len(audio) == 0:
            self._set_state(State.IDLE)
            return
        duration = len(audio) / self.config.sample_rate
        if duration < 0.25:
            logger.info("audio too short: %.2fs, skip", duration)
            self._set_state(State.IDLE)
            return

        self._set_state(State.PROCESSING)
        threading.Thread(
            target=self._recognize_and_inject,
            args=(audio,),
            daemon=True,
        ).start()

    def _recognize_and_inject(self, audio) -> None:
        try:
            res = self.recognizer.recognize(
                audio,
                language=self.config.language,
                hotwords=self.config.hotwords,
                sample_rate=self.config.sample_rate,
            )
            if res is None or not res.text:
                logger.info("empty recognition result")
                self._set_state(State.IDLE)
                return
            logger.info(
                "recognized [%.2fs RTF=%.2f]: %r", res.duration, res.rtf, res.text
            )
            # 注入文字
            time.sleep(0.05)
            if self.config.input_method == "type":
                inject_via_type(res.text)
            else:
                inject_via_paste(
                    res.text,
                    paste_key=self.config.paste_key,
                    terminal_paste_key=self.config.terminal_paste_key,
                )
            # 记录历史
            item = HistoryItem(
                text=res.text,
                duration=res.duration,
                rtf=res.rtf,
                ts=time.time(),
                language=self.config.language,
            )
            self.history.add(item)
            self.recognized.emit(item)
        finally:
            self._set_state(State.IDLE)

    def _on_recognized(self, item: HistoryItem) -> None:
        # 在托盘 tooltip 显示最近一句（截断）
        snippet = item.text[:40] + ("..." if len(item.text) > 40 else "")
        self.tray.setToolTip(
            f"Voice Input · 待机（按住 {self.hotkey.description}）\n上次: {snippet}"
        )
