"""
SenseVoice 全局语音输入工具 (X11 / Linux)
- 按住 Right Ctrl 说话，松开停止识别并把文字打到光标位置
- 支持中英文混说、自动加标点
- 模型：iic/SenseVoiceSmall（首次启动自动下载 ~234MB）
"""

import argparse
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from pynput import keyboard

# ---- 默认参数 ----
SAMPLE_RATE = 16000
CHANNELS = 1
MIN_DURATION = 0.3  # 录音太短忽略（秒）
MAX_DURATION = 60   # 单次最长录音
DEFAULT_HOTKEY = "ctrl_r"  # 右 Ctrl 作为 push-to-talk 键
SENSEVOICE_TAG_RE = re.compile(r"<\|[^|]*\|>")


def load_model(device: str):
    """延迟导入 funasr，避免启动慢"""
    from funasr import AutoModel

    print(f"[init] 加载 SenseVoiceSmall 到 {device} ...", flush=True)
    t0 = time.time()
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device=device,
        disable_update=True,
        trust_remote_code=False,
    )
    print(f"[init] 模型加载完毕，耗时 {time.time()-t0:.1f}s", flush=True)
    return model


def clean_text(raw: str) -> str:
    """SenseVoice 输出形如 <|zh|><|NEUTRAL|><|Speech|><|woitn|>正文，去掉标签"""
    return SENSEVOICE_TAG_RE.sub("", raw).strip()


def type_text_xdotool(text: str):
    """xdotool type 直接打字（中文快速输入容易丢字/乱序，仅作 fallback）"""
    if not text:
        return
    subprocess.run(
        ["xdotool", "type", "--delay", "12", "--clearmodifiers", text],
        check=False,
    )


# 常见终端模拟器的 WM_CLASS（小写），需要用 Shift+Ctrl+V 粘贴
TERMINAL_CLASSES = {
    # 传统 X11 终端（class 名通常含 "term"，兜底也能匹配）
    "gnome-terminal", "gnome-terminal-server",
    "xterm", "uxterm",
    "konsole",
    "alacritty",
    "kitty",
    "terminator",
    "tilix",
    "wezterm", "org.wezfurlong.wezterm",
    "xfce4-terminal",
    "deepin-terminal",
    "tilda", "guake",
    "qterminal",
    "warp-terminal",
    "io.elementary.terminal",
    # Electron / Web 技术栈终端（class 名不带 "term"，必须显式白名单）
    "tabby",
    "hyper",
    "extraterm",
    "rio",
}


_WM_CLASS_RE = re.compile(r'"([^"]+)"')


def detect_active_window_class() -> str:
    """返回当前焦点窗口的 WM_CLASS（小写），失败返回空串
    优先用 xdotool getwindowclassname（新版本），不行用 xprop 兜底。
    """
    # 方案 A: xdotool getwindowclassname（新版本才有）
    try:
        r = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowclassname"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().lower()
    except Exception:
        pass

    # 方案 B: xprop（几乎所有 X11 系统都有）
    try:
        wid = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True,
            text=True,
            timeout=1,
        ).stdout.strip()
        if not wid:
            return ""
        r = subprocess.run(
            ["xprop", "-id", wid, "WM_CLASS"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        # 形如: WM_CLASS(STRING) = "gnome-terminal-server", "Gnome-terminal"
        # 取等号后面最后一个引号串（一般是 class name）
        if "=" in r.stdout:
            vals = _WM_CLASS_RE.findall(r.stdout.split("=", 1)[1])
            if vals:
                return vals[-1].lower()
    except Exception:
        pass

    return ""


def is_terminal_window() -> bool:
    cls = detect_active_window_class()
    if not cls:
        return False
    if cls in TERMINAL_CLASSES:
        return True
    # 兜底：class 名含 "term" 的几乎都是终端
    return "term" in cls


def _xclip_set(selection: str, data: bytes):
    subprocess.run(
        ["xclip", "-selection", selection],
        input=data,
        timeout=2,
        check=False,
    )


def type_text_paste(
    text: str,
    paste_key: str = "ctrl+v",
    terminal_paste_key: str = "ctrl+shift+v",
    verbose: bool = True,
):
    """剪贴板 + 粘贴快捷键（中文最稳，自动适配终端）

    同时写入 CLIPBOARD 和 PRIMARY 两个 selection，兼容性最好：
      - Ctrl+V / Ctrl+Shift+V 用 CLIPBOARD
      - Shift+Insert 用 PRIMARY
    """
    if not text:
        return

    # 1. 备份当前剪贴板（粘贴完恢复，不污染用户剪贴板）
    try:
        orig_clip = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True,
            timeout=1,
        ).stdout
    except Exception:
        orig_clip = b""

    # 2. 写入 CLIPBOARD + PRIMARY（覆盖更多粘贴键场景）
    try:
        _xclip_set("clipboard", text.encode("utf-8"))
        _xclip_set("primary", text.encode("utf-8"))
    except Exception as e:
        print(f"[err] 写剪贴板失败: {e}，回退到 xdotool type", flush=True)
        type_text_xdotool(text)
        return

    # 3. 等剪贴板生效
    time.sleep(0.06)

    # 4. 检测焦点窗口，决定粘贴键
    cls = detect_active_window_class()
    in_term = bool(cls) and (cls in TERMINAL_CLASSES or "term" in cls)
    chosen_key = terminal_paste_key if in_term else paste_key

    if verbose:
        print(
            f"[paste] active_class={cls!r}  is_terminal={in_term}  key={chosen_key}",
            flush=True,
        )

    subprocess.run(
        ["xdotool", "key", "--clearmodifiers", chosen_key],
        check=False,
    )

    # 5. 等粘贴动作完成再恢复原剪贴板
    time.sleep(0.25)
    _xclip_set("clipboard", orig_clip)


def parse_hotkey(spec: str):
    """
    解析快捷键配置，返回一个可与 pynput Key 对象比较的 matcher。
    支持:
      - 特殊键名: ctrl_r / alt_r / f4 / f9 / shift / cmd ...
      - 字符键:   a / 1 / `（直接传字符）
      - VK 码:    vk:269025067  （keytest.py 输出的 vk 数字）
    """
    spec = spec.strip()

    # 1) vk:数字
    if spec.startswith("vk:"):
        target_vk = int(spec[3:])

        def match(key):
            return getattr(key, "vk", None) == target_vk

        return match, f"vk={target_vk}"

    # 2) 特殊键 (pynput keyboard.Key 枚举)
    if hasattr(keyboard.Key, spec):
        target = getattr(keyboard.Key, spec)

        def match(key):
            return key == target

        return match, spec

    # 3) 单字符
    if len(spec) == 1:
        target = keyboard.KeyCode.from_char(spec)

        def match(key):
            return getattr(key, "char", None) == spec

        return match, f"char '{spec}'"

    raise ValueError(
        f"无法解析快捷键 '{spec}'。可选: "
        f"ctrl_r/alt_r/f1~f12 等特殊键，或单字符，或 vk:数字（先跑 keytest.py 探测）"
    )


class VoiceInput:
    def __init__(
        self,
        model,
        hotkey_name: str,
        language: str = "zh",
        input_device: int | None = None,
        input_method: str = "paste",
        paste_key: str = "ctrl+v",
        terminal_paste_key: str = "ctrl+shift+v",
    ):
        self.model = model
        self.language = language
        self.input_device = input_device
        self.input_method = input_method
        self.paste_key = paste_key
        self.terminal_paste_key = terminal_paste_key
        self.hotkey_name = hotkey_name
        self.match_hotkey, self.hotkey_desc = parse_hotkey(hotkey_name)
        self.recording = False
        self.audio_chunks: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None
        self.lock = threading.Lock()
        self.processing = False

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}", flush=True)
        if self.recording:
            self.audio_chunks.append(indata.copy())

    def start_recording(self):
        with self.lock:
            if self.recording or self.processing:
                return
            self.recording = True
            self.audio_chunks = []
            try:
                self.stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    callback=self.audio_callback,
                    dtype="float32",
                    device=self.input_device,
                )
                self.stream.start()
            except Exception as e:
                self.recording = False
                print(f"[err] 打开麦克风失败: {e}", flush=True)
                return
            print("\n🎙️  录音中... (松开停止)", flush=True)

    def stop_recording(self):
        with self.lock:
            if not self.recording:
                return
            self.recording = False
            self.processing = True
            stream = self.stream
            self.stream = None
            chunks = self.audio_chunks
            self.audio_chunks = []

        try:
            if stream is not None:
                stream.stop()
                stream.close()
        except Exception as e:
            print(f"[warn] 关闭麦克风失败: {e}", flush=True)

        try:
            self._recognize_and_type(chunks)
        finally:
            with self.lock:
                self.processing = False

    def _recognize_and_type(self, chunks):
        if not chunks:
            print("[warn] 没录到音频", flush=True)
            return

        audio = np.concatenate(chunks, axis=0).flatten().astype(np.float32)
        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_DURATION:
            print(f"[skip] 录音太短 {duration:.2f}s", flush=True)
            return
        if duration > MAX_DURATION:
            audio = audio[: int(MAX_DURATION * SAMPLE_RATE)]
            print(f"[trim] 截断到 {MAX_DURATION}s", flush=True)

        # 音量诊断（识别不准 90% 是这里出问题）
        peak = float(np.max(np.abs(audio)))
        if peak < 0.05:
            print(
                f"[warn] 录音峰值仅 {peak:.3f}，几乎是静音 → 检查麦克风/输入音量/设备选择",
                flush=True,
            )
        elif peak < 0.15:
            print(f"[warn] 录音峰值 {peak:.3f} 偏小，建议调高输入音量", flush=True)

        t0 = time.time()
        try:
            res = self.model.generate(
                input=audio,
                cache={},
                language=self.language,
                use_itn=True,
                batch_size_s=60,
            )
        except Exception as e:
            print(f"[err] 识别失败: {e}", flush=True)
            return

        if not res:
            print("[warn] 模型返回空", flush=True)
            return

        text = clean_text(res[0].get("text", ""))
        dt = time.time() - t0
        rtf = dt / max(duration, 1e-6)
        print(f"✅ [{dt:.2f}s, RTF={rtf:.2f}] {text!r}", flush=True)
        if text:
            # 给一点点延迟，等用户的按键完全释放，避免冲突
            time.sleep(0.05)
            if self.input_method == "type":
                type_text_xdotool(text)
            else:
                type_text_paste(
                    text,
                    paste_key=self.paste_key,
                    terminal_paste_key=self.terminal_paste_key,
                )

    # ---- 快捷键回调 ----
    def on_press(self, key):
        if self.match_hotkey(key):
            self.start_recording()

    def on_release(self, key):
        if self.match_hotkey(key):
            # 在独立线程里跑识别，避免阻塞键盘监听
            threading.Thread(target=self.stop_recording, daemon=True).start()
        elif key == keyboard.Key.esc and self._is_double_esc():
            print("[exit] 双击 Esc 退出", flush=True)
            return False

    _last_esc = 0.0

    def _is_double_esc(self) -> bool:
        now = time.time()
        if now - self._last_esc < 0.4:
            return True
        self._last_esc = now
        return False

    def run(self):
        print(
            f"[ready] 按住 [{self.hotkey_desc}] 说话，松开识别并粘贴；双击 Esc 退出",
            flush=True,
        )
        with keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        ) as listener:
            listener.join()


def check_deps(input_method: str):
    if subprocess.run(["which", "xdotool"], capture_output=True).returncode != 0:
        print("[fatal] 没找到 xdotool，请先运行: sudo apt install -y xdotool", flush=True)
        sys.exit(1)
    if input_method == "paste":
        if subprocess.run(["which", "xclip"], capture_output=True).returncode != 0:
            print(
                "[fatal] 没找到 xclip (剪贴板粘贴需要)，请先运行: sudo apt install -y xclip\n"
                "        或改用 --input-method type （注意中文容易丢字）",
                flush=True,
            )
            sys.exit(1)


def list_audio_devices():
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


def main():
    parser = argparse.ArgumentParser(description="SenseVoice 全局语音输入")
    parser.add_argument(
        "--device",
        default="cuda:0",
        help="cuda:0 / cpu （默认 cuda:0）",
    )
    parser.add_argument(
        "--hotkey",
        default=DEFAULT_HOTKEY,
        help="pynput Key 名，如 ctrl_r / alt_r / f4 / f9 （默认 ctrl_r）",
    )
    parser.add_argument(
        "--language",
        default="zh",
        choices=["auto", "zh", "en", "yue", "ja", "ko"],
        help="识别语言（默认 zh 中文最准；中英混说选 auto；纯英文 en）",
    )
    parser.add_argument(
        "--input-device",
        type=int,
        default=None,
        help="麦克风设备 idx（不指定则用系统默认，先 --list-devices 查看）",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="列出所有音频输入设备后退出",
    )
    parser.add_argument(
        "--input-method",
        default="paste",
        choices=["paste", "type"],
        help="paste=剪贴板+Ctrl+V（中文最稳，默认）；type=xdotool直接打（快但中文易丢字）",
    )
    parser.add_argument(
        "--paste-key",
        default="ctrl+v",
        help="非终端粘贴键（xdotool key 格式，默认 ctrl+v）",
    )
    parser.add_argument(
        "--terminal-paste-key",
        default="ctrl+shift+v",
        help="终端粘贴键（默认 ctrl+shift+v；GNOME Terminal/Alacritty/Kitty 等；"
        "也可以用 shift+Insert / ctrl+Insert 等）",
    )
    args = parser.parse_args()

    if args.list_devices:
        list_audio_devices()
        return

    check_deps(args.input_method)
    print(f"[init] 使用麦克风: idx={args.input_device if args.input_device is not None else '默认'}", flush=True)
    print(f"[init] 识别语言: {args.language}", flush=True)
    print(f"[init] 输入方式: {args.input_method}", flush=True)
    model = load_model(args.device)
    app = VoiceInput(
        model,
        hotkey_name=args.hotkey,
        language=args.language,
        input_device=args.input_device,
        input_method=args.input_method,
        paste_key=args.paste_key,
        terminal_paste_key=args.terminal_paste_key,
    )
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n[exit] Ctrl+C 退出", flush=True)


if __name__ == "__main__":
    main()
