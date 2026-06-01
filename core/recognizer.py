"""SenseVoice 加载 + 识别（支持热词）"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

TAG_RE = re.compile(r"<\|[^|]*\|>")


@dataclass
class RecognizeResult:
    text: str
    raw: str
    duration: float        # 录音时长（秒）
    elapsed: float         # 识别耗时（秒）
    rtf: float


class Recognizer:
    def __init__(self, device: str = "cuda:0") -> None:
        self.device = device
        self.model = None  # 延迟加载

    def load(self) -> None:
        if self.model is not None:
            return
        from funasr import AutoModel  # 延迟 import 避免启动慢
        logger.info("loading SenseVoiceSmall on %s ...", self.device)
        t0 = time.time()
        self.model = AutoModel(
            model="iic/SenseVoiceSmall",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device=self.device,
            disable_update=True,
            trust_remote_code=False,
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
        try:
            kwargs = dict(
                input=audio,
                cache={},
                language=language,
                use_itn=True,
                batch_size_s=60,
            )
            if hotwords.strip():
                kwargs["hotword"] = hotwords.strip()
            res = self.model.generate(**kwargs)
        except Exception as e:
            logger.error("recognize failed: %s", e)
            return None

        if not res:
            return None
        raw = res[0].get("text", "")
        text = TAG_RE.sub("", raw).strip()
        elapsed = time.time() - t0
        rtf = elapsed / max(duration, 1e-6)
        return RecognizeResult(
            text=text, raw=raw, duration=duration, elapsed=elapsed, rtf=rtf
        )
