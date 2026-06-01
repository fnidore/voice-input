"""
音频诊断 + 识别测试一站式工具
用法:
  python audio_test.py --list                    # 只列设备
  python audio_test.py                           # 默认设备录 5s + 分析 + 识别
  python audio_test.py --device 5                # 用 5 号设备
  python audio_test.py --seconds 8 --language zh # 8s + 强制中文
  python audio_test.py --no-asr                  # 只录音分析，不跑模型
"""

import argparse
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
TAG_RE = re.compile(r"<\|[^|]*\|>")


def list_devices():
    print("=" * 78)
    print(f"{'idx':>4}  {'name':46} {'max_in':>7} {'default_sr':>11}")
    print("=" * 78)
    default_in = sd.default.device[0] if sd.default.device else -1
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            mark = "  ★ 默认" if i == default_in else ""
            print(
                f"{i:>4}  {d['name'][:46]:46} "
                f"{d['max_input_channels']:>7} "
                f"{int(d['default_samplerate']):>11}{mark}"
            )
    print("=" * 78)


def record(seconds: int, device):
    dev_show = device if device is not None else "默认"
    print(f"\n[rec] 即将用设备 [{dev_show}] 录音 {seconds}s")
    for n in (3, 2, 1):
        print(f"[rec] {n}...", flush=True)
        time.sleep(1)
    print("[rec] 🎙️  说话！(建议念一句: 今天天气真好，I am using SenseVoice)", flush=True)
    audio = sd.rec(
        int(seconds * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()
    print("[rec] ✅ 录音结束")
    return audio.flatten()


def analyze(audio: np.ndarray):
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio ** 2)))
    print("\n[stats]")
    print(f"  峰值: {peak:.3f}   推荐 0.3~0.9，<0.05 太小，>0.99 削顶")
    print(f"  RMS : {rms:.4f}   推荐 >0.02")
    if peak < 0.05:
        verdict = "❌ 录音几乎是静音 → 麦克风没工作 / 选错设备 / 输入音量为 0"
    elif peak < 0.15:
        verdict = "⚠️  录音音量偏小 → 调高系统输入音量，或离麦克风近一点"
    elif peak > 0.99:
        verdict = "⚠️  削顶/爆音 → 把系统输入音量调低"
    else:
        verdict = "✅ 音量 OK"
    print(f"  判定: {verdict}")
    return peak >= 0.05


def save_wav(audio: np.ndarray, path: Path):
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    print(f"\n[wav] 已保存 {path}")
    print(f"      回放: aplay {path}")


def recognize(audio: np.ndarray, language: str):
    from funasr import AutoModel

    print(f"\n[asr] 加载 SenseVoiceSmall (language={language}) ...")
    t0 = time.time()
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cuda:0",
        disable_update=True,
    )
    print(f"[asr] 模型加载 {time.time()-t0:.1f}s")

    t0 = time.time()
    res = model.generate(
        input=audio,
        cache={},
        language=language,
        use_itn=True,
        batch_size_s=60,
    )
    dt = time.time() - t0
    raw = res[0].get("text", "") if res else ""
    text = TAG_RE.sub("", raw).strip()
    print(f"[asr] 识别耗时 {dt:.2f}s")
    print(f"[asr] 原始输出: {raw!r}")
    print(f"[asr] 清洗结果: {text!r}")
    return text


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true", help="只列设备")
    p.add_argument("--device", type=int, default=None, help="输入设备 index")
    p.add_argument("--seconds", type=int, default=5, help="录音秒数")
    p.add_argument(
        "--language",
        default="zh",
        choices=["auto", "zh", "en", "yue", "ja", "ko"],
        help="识别语言（默认 zh，比 auto 更准）",
    )
    p.add_argument("--no-asr", action="store_true", help="只录音，不跑模型")
    args = p.parse_args()

    print("==> 步骤 1: 音频输入设备清单")
    list_devices()

    if args.list:
        return

    print("\n==> 步骤 2: 录音并分析")
    audio = record(args.seconds, device=args.device)
    ok = analyze(audio)
    wav_path = Path(__file__).parent / "test_recording.wav"
    save_wav(audio, wav_path)

    if args.no_asr:
        return

    if not ok:
        print("\n[stop] 录音质量太差，先解决录音问题再跑识别")
        sys.exit(1)

    print("\n==> 步骤 3: 识别测试")
    recognize(audio, args.language)

    print("\n" + "=" * 78)
    print("📌 排错指南:")
    print("  · 录音不清晰 → aplay test_recording.wav 回放确认")
    print("  · 音量偏小  → 系统设置 → 声音 → 输入 → 调大音量")
    print("  · 设备选错  → 用 --device <上面表格里的 idx> 换个麦克风重测")
    print("  · 中文不准  → 把 --language 改成 zh（默认就是 zh）")
    print("  · 全英文    → --language en")
    print("=" * 78)


if __name__ == "__main__":
    main()
