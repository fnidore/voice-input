"""提示音：用 numpy 生成 ding 音并通过 sounddevice 播放（无外部依赖）"""

from __future__ import annotations

import logging
import threading

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100


def _tone(freq: float, duration: float, volume: float = 0.5) -> np.ndarray:
    """单音 + 指数衰减 envelope"""
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0, duration, n, endpoint=False)
    wave = np.sin(2 * np.pi * freq * t)
    envelope = np.exp(-3.5 * t / duration)
    return (wave * envelope * volume).astype(np.float32)


def _ding_start(volume: float) -> np.ndarray:
    """开始录音: 高音 ding（C5）"""
    return _tone(880.0, 0.12, volume)


def _ding_stop(volume: float) -> np.ndarray:
    """结束录音: 低音 dong（C4）"""
    return _tone(523.0, 0.12, volume)


def _play_async(samples: np.ndarray) -> None:
    def _run():
        try:
            sd.play(samples, SAMPLE_RATE, blocking=True)
        except Exception as e:
            logger.warning("sound play failed: %s", e)

    threading.Thread(target=_run, daemon=True).start()


def play_start(volume: float = 0.5) -> None:
    _play_async(_ding_start(volume))


def play_stop(volume: float = 0.5) -> None:
    _play_async(_ding_stop(volume))
