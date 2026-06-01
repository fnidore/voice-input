"""识别历史：环形缓冲 + JSON 持久化"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import HISTORY_FILE, ensure_dirs

logger = logging.getLogger(__name__)


@dataclass
class HistoryItem:
    text: str
    duration: float       # 录音时长（秒）
    rtf: float            # 实时因子
    ts: float             # unix 秒
    language: str         # 识别语言


class History:
    def __init__(self, max_items: int = 20, path: Path | None = None) -> None:
        self.max_items = max_items
        self.path = path or HISTORY_FILE
        self.items: deque[HistoryItem] = deque(maxlen=max_items)
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for d in raw[-self.max_items:]:
                self.items.append(HistoryItem(**d))
        except Exception as e:
            logger.warning("history load failed: %s", e)

    def add(self, item: HistoryItem) -> None:
        self.items.append(item)
        self.save()

    def clear(self) -> None:
        self.items.clear()
        self.save()

    def save(self) -> None:
        ensure_dirs()
        try:
            self.path.write_text(
                json.dumps([asdict(i) for i in self.items], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("history save failed: %s", e)

    def recent(self) -> list[HistoryItem]:
        return list(self.items)
