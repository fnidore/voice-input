"""配置管理：加载 / 保存 / 默认值"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "voice-input"
CONFIG_FILE = CONFIG_DIR / "config.json"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "voice-input"
LOG_DIR = DATA_DIR / "logs"
HISTORY_FILE = DATA_DIR / "history.json"


@dataclass
class Config:
    # ---- 识别相关 ----
    model_preset: str = "sensevoice"      # 见 core/presets.py PRESETS
    model_device: str = "cuda:0"          # cuda:0 / cpu（cuda 不可用会自动回退 cpu）
    language: str = "zh"                  # auto / zh / en / yue / ja / ko（仅多语种模型）
    hotwords: str = ""                    # 空格分隔的热词列表

    # ---- 录音相关 ----
    input_device_index: int | None = None  # None = 系统默认
    sample_rate: int = 16000

    # ---- 快捷键 ----
    hotkey: str = "f4"                    # pynput Key 名 / 字符 / vk:数字

    # ---- 输入注入 ----
    input_method: str = "paste"           # paste / type
    paste_key: str = "ctrl+v"
    terminal_paste_key: str = "ctrl+shift+v"

    # ---- 提示音 ----
    play_sound: bool = True
    sound_volume: float = 0.5             # 0~1

    # ---- 自启动 ----
    autostart_enabled: bool = False

    # ---- 历史记录 ----
    history_max: int = 20

    def save(self, path: Path | None = None) -> None:
        target = path or CONFIG_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("config saved to %s", target)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        target = path or CONFIG_FILE
        if not target.exists():
            logger.info("config not found, using defaults")
            cfg = cls()
            cfg.save(target)
            return cfg
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.error("bad config (%s), backing up and using defaults", e)
            target.rename(target.with_suffix(".bad"))
            cfg = cls()
            cfg.save(target)
            return cfg
        # 用 dataclass 默认值兜底未知字段
        known = {f.name for f in cls.__dataclass_fields__.values()}
        cleaned = {k: v for k, v in data.items() if k in known}
        return cls(**{**asdict(cls()), **cleaned})


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
