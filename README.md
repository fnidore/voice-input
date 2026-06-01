# Voice Input · 全局语音输入（SenseVoice + PySide6 GUI + Linux/X11）

按住快捷键说话，松开就把识别结果打到当前光标位置。中英文混说、自动加标点。
带系统托盘 GUI、设置窗口、识别历史、热词支持、开机自启。

## 开发 / 测试环境（作者实测）

- AMD Ryzen AI 7 H 350 / 30GB RAM
- RTX 5060 Laptop 8GB（Blackwell, sm_120, 需要 PyTorch ≥ 2.7 + CUDA 12.8）
- Ubuntu 22.04, X11

> ⚠️ 目前仅支持 **Linux + X11**（依赖 xdotool/xclip）。Wayland、macOS、Windows 暂未支持。

## 项目结构

```
voice_input/
├── core/                  ← 业务核心（无 GUI 依赖）
│   ├── config.py          ← 配置 ~/.config/voice-input/config.json
│   ├── logger.py          ← 日志 ~/.local/share/voice-input/logs/
│   ├── audio.py           ← 录音 + 音量回调
│   ├── recognizer.py      ← SenseVoice 推理 + 热词
│   ├── inject.py          ← 剪贴板粘贴（自动适配终端）
│   ├── hotkey.py          ← 全局快捷键
│   ├── history.py         ← 识别历史 ~/.local/share/voice-input/history.json
│   └── sound.py           ← 录音提示音（开始/结束 ding）
├── gui/                   ← PySide6 界面层
│   ├── icons.py           ← 动态生成三态托盘图标
│   ├── volume_meter.py    ← 实时音量条
│   ├── hotkey_capture.py  ← 自定义快捷键按钮
│   ├── settings_window.py ← 设置窗口（5 个 tab）
│   ├── tray_app.py        ← 托盘应用 + 状态机
│   └── autostart.py       ← systemd 自启管理
├── voice_input_gui.py     ← GUI 主入口（推荐）
├── main.py                ← CLI 入口（保留，无需 GUI 时用）
├── run_gui.sh             ← 启动 GUI
├── run.sh                 ← 启动 CLI（兼容老版本）
├── install_system_deps.sh ← 装 xdotool/xclip/portaudio
├── install_autostart.sh   ← 安装 systemd user service
└── setup_env.sh           ← 建 conda 环境 + 装 PyTorch/FunASR
```

## 三步装好

```bash
# 0) 克隆仓库
git clone https://github.com/fnidore/voice-input.git
cd voice-input

# 1) 系统依赖（一次性，要 sudo）
bash install_system_deps.sh

# 2) 建 conda 环境 + 装 PyTorch + FunASR + PySide6 （首次 10-20 分钟）
bash setup_env.sh

# 3) 启动 GUI
bash run_gui.sh
```

启动后会出现一个**麦克风图标**在系统托盘里：
- 灰色 = 待机
- 红色 = 录音中（按住 F4 时）
- 蓝色 = 识别中
- 红色 = 错误

**双击托盘图标** 打开设置窗口；**右键** 看菜单（暂停/重新加载模型/退出）。

## GUI 设置窗口（双击托盘）

5 个 Tab：

| Tab | 内容 |
|---|---|
| **基础** | 模型设备 (cuda:0/cpu)、语言、输入方式、麦克风（带音量条测试按钮）、提示音、开机自启 |
| **快捷键** | 自定义说话快捷键（点按钮捕获）、自定义粘贴键 |
| **热词** | 多行编辑，空格分隔，让识别更准（如 `涛涛鱼 SenseVoice 机械臂`） |
| **历史** | 最近 20 条识别结果，双击复制到剪贴板 |
| **日志** | 实时显示最后 200 行日志，方便排查 |

## 开机自启

打开 GUI 设置 → 基础 → 勾选「开机自启」→ 保存。

或者命令行：

```bash
# 启用自启 + 立即启动
bash install_autostart.sh

# 禁用
bash install_autostart.sh disable

# 完全卸载
bash install_autostart.sh remove

# 查状态
systemctl --user status voice-input.service

# 看日志
journalctl --user -u voice-input.service -f
```

## CLI 模式（不要 GUI 时用）

```bash
bash run.sh                          # 默认 F4 + cuda:0 + zh
bash run.sh --hotkey f9 --device cpu --language auto
bash run.sh --list-devices           # 列麦克风
bash run.sh --input-device 5         # 用 5 号麦克风
```

## 期望性能

| 模式 | RTF | 说 5 秒识别耗时 |
|---|---|---|
| RTX 5060 GPU | ~0.02 | ~0.1s |
| CPU (Ryzen H350) | ~0.1 | ~0.5s |

## 常见坑

**1. GUI 启动看不到托盘图标？**
GNOME 默认不显示传统托盘，要装扩展：
```bash
sudo apt install gnome-shell-extension-appindicator
# 然后到 https://extensions.gnome.org/ 启用 AppIndicator 扩展，注销重登
```

**2. systemd 服务起来但没界面？**
service 文件里默认 `DISPLAY=:1`，如果你的 X server 不是 `:1`，改 service 或 GUI 设置里的环境。
```bash
echo $DISPLAY        # 看实际值
# 编辑 ~/.config/systemd/user/voice-input.service 的 Environment=DISPLAY=...
systemctl --user daemon-reload && systemctl --user restart voice-input.service
```

**3. 录音爆音 / 削顶**
设置 → 基础 → 测试 5 秒看音量条。如果一直撞红，命令行调音量：
```bash
pactl set-source-volume @DEFAULT_SOURCE@ 25%
```

**4. PyTorch CUDA: False**
RTX 5060 Blackwell sm_120，必须 CUDA 12.8 + PyTorch ≥2.7。重跑 `setup_env.sh`。

**5. 模型下载失败**
ModelScope 国内很快，关掉代理重试即可。

**6. 终端粘贴不出字**
默认对 Tabby/GNOME Terminal/Alacritty 等都做了识别。冷门终端可在设置 → 快捷键 → 「终端粘贴键」改成 `shift+Insert`。

## 数据/配置位置

| 路径 | 内容 |
|---|---|
| `~/.config/voice-input/config.json` | 用户配置 |
| `~/.local/share/voice-input/history.json` | 识别历史 |
| `~/.local/share/voice-input/logs/voice-input.log` | 日志（滚动 5MB×5） |
| `~/.config/systemd/user/voice-input.service` | 自启 service 文件 |
| `~/.cache/modelscope/hub/models/iic/SenseVoiceSmall` | 模型权重 |

## 卸载

```bash
# 1. 关自启
bash install_autostart.sh remove

# 2. 退 GUI（右键托盘 → 退出）

# 3. 删数据（可选）
rm -rf ~/.config/voice-input ~/.local/share/voice-input

# 4. 删 conda 环境（可选）
conda env remove -n voice_input

# 5. 删项目目录
rm -rf voice-input
```

## 致谢

- [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) / [FunASR](https://github.com/modelscope/FunASR) —— 语音识别模型
- [PySide6](https://doc.qt.io/qtforpython/) —— GUI 框架

## License

[MIT](./LICENSE) © 2026 fnidore
