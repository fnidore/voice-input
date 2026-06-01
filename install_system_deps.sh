#!/usr/bin/env bash
# 安装系统级依赖（一次性，需要 sudo）
set -e

echo "==> 安装 xdotool / xclip / x11-utils(xprop) / portaudio / libxcb（PySide6 需要）..."
sudo apt update
sudo apt install -y \
  xdotool xclip x11-utils \
  portaudio19-dev libportaudio2 libasound2-dev \
  libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0

echo "==> 检查 X11 环境..."
if [ "$XDG_SESSION_TYPE" != "x11" ]; then
  echo "[warn] 当前不是 X11 ($XDG_SESSION_TYPE)，xdotool 在 Wayland 下无法工作"
  echo "       如果在 Wayland，请改用 ydotool"
fi

echo "==> 完成"
