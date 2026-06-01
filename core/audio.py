"""录音：sounddevice 流式录音 + 音量回调"""

from __future__ import annotations

import logging
import threading
from typing import Callable

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

CHANNELS = 1


class Recorder:
    """按住录音 / 松开取数据。回调线程里推音量给 UI。"""

    def __init__(
        self,
        sample_rate: int = 16000,
        input_device: int | None = None,
        on_level: Callable[[float], None] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.input_device = input_device
        self.on_level = on_level
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._running = False

    def list_devices(self) -> list[dict]:
        devs = []
        default_in = sd.default.device[0] if sd.default.device else -1
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                devs.append({
                    "index": i,
                    "name": d["name"],
                    "max_input_channels": d["max_input_channels"],
                    "default_samplerate": int(d["default_samplerate"]),
                    "is_default": i == default_in,
                })
        return devs

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.debug("audio status: %s", status)
        if not self._running:
            return
        self._chunks.append(indata.copy())
        if self.on_level is not None:
            try:
                peak = float(np.max(np.abs(indata)))
                self.on_level(peak)
            except Exception:
                pass

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return False
            self._chunks = []
            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=CHANNELS,
                    callback=self._callback,
                    dtype="float32",
                    device=self.input_device,
                )
                self._stream.start()
                self._running = True
                return True
            except Exception as e:
                logger.error("open mic failed: %s", e)
                self._stream = None
                return False

    def stop(self) -> np.ndarray | None:
        with self._lock:
            if not self._running:
                return None
            self._running = False
            stream = self._stream
            self._stream = None
            chunks = self._chunks
            self._chunks = []

        try:
            if stream is not None:
                stream.stop()
                stream.close()
        except Exception as e:
            logger.warning("close stream failed: %s", e)

        if not chunks:
            return None
        return np.concatenate(chunks, axis=0).flatten().astype(np.float32)
