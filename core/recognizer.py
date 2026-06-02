"""模型加载 + 识别：按预设切换模型，支持热词，cuda 不可用自动回退 cpu。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np

from core.presets import DEFAULT_PRESET, clean_text, get_preset

logger = logging.getLogger(__name__)


@dataclass
class RecognizeResult:
    text: str
    raw: str
    duration: float        # 录音时长（秒）
    elapsed: float         # 识别耗时（秒）
    rtf: float


def resolve_device(device: str) -> str:
    """cuda 不可用（CPU 版 PyTorch / 无 GPU）时回退 cpu，避免加载崩溃。"""
    if device.startswith("cuda"):
        try:
            import torch
            if not torch.cuda.is_available():
                logger.warning("cuda 不可用，回退 cpu（CPU 版 PyTorch 或无 GPU）")
                return "cpu"
        except Exception as e:
            logger.warning("torch 检测失败(%s)，回退 cpu", e)
            return "cpu"
    return device


class Recognizer:
    def __init__(self, preset_key: str = DEFAULT_PRESET, device: str = "cpu") -> None:
        self.preset = get_preset(preset_key)
        self.device = device
        self.model = None  # 延迟加载

    def load(self) -> None:
        if self.model is not None:
            return
        self.device = resolve_device(self.device)
        from funasr import AutoModel  # 延迟 import 避免启动慢
        logger.info("loading %s on %s ...", self.preset.model_id, self.device)
        t0 = time.time()
        self.model = AutoModel(
            model=self.preset.model_id,
            device=self.device,
            disable_update=True,
            trust_remote_code=False,
            **self.preset.load_kwargs,
        )
        logger.info("model loaded in %.1fs", time.time() - t0)

    def recognize(
        self,
        audio: np.ndarray,
        language: str = "zh",
        hotwords: str = "",
        sample_rate: int = 16000,
    ) -> RecognizeResult | None:
        if self.model is None:
            self.load()
        if audio is None or len(audio) == 0:
            return None

        duration = len(audio) / sample_rate
        t0 = time.time()
        p = self.preset
        try:
            # 按预设能力透传参数：不支持的不传，避免该模型报错
            kwargs = dict(input=audio, cache={}, **p.gen_kwargs)
            if p.accepts_language:
                kwargs["language"] = language
            if p.accepts_itn:
                kwargs["use_itn"] = True
            if p.accepts_hotword and hotwords.strip():
                kwargs["hotword"] = hotwords.strip()
            res = self.model.generate(**kwargs)
        except Exception as e:
            logger.error("recognize failed: %s", e)
            return None

        if not res:
            return None
        raw = res[0].get("text", "")
        text = clean_text(raw)
        elapsed = time.time() - t0
        rtf = elapsed / max(duration, 1e-6)
        return RecognizeResult(
            text=text, raw=raw, duration=duration, elapsed=elapsed, rtf=rtf
        )
