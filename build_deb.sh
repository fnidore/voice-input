#!/usr/bin/env bash
# 把 PyInstaller onedir 产物（dist/voice-input/）打成 .deb 安装包。
# 用法: bash build_deb.sh [版本号]   默认 0.1.0
set -euo pipefail

VERSION="${1:-0.1.0}"
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$PROJ/dist/voice-input"
ARCH="amd64"
PKG="voice-input_${VERSION}_${ARCH}"
BUILD="$PROJ/build/deb/$PKG"

if [ ! -d "$DIST" ]; then
    echo "❌ 未找到 $DIST，请先运行: pyinstaller voice_input.spec"
    exit 1
fi

echo ">>> 清理旧构建目录"
rm -rf "$BUILD"
mkdir -p "$BUILD/DEBIAN" "$BUILD/opt/voice-input" "$BUILD/usr/bin" "$BUILD/usr/share/applications"

echo ">>> 复制程序到 /opt/voice-input"
cp -r "$DIST/." "$BUILD/opt/voice-input/"

echo ">>> 写 /usr/bin 启动器"
cat > "$BUILD/usr/bin/voice-input" <<'EOF'
#!/bin/sh
exec /opt/voice-input/voice-input "$@"
EOF
chmod 755 "$BUILD/usr/bin/voice-input"

echo ">>> 写 desktop 入口"
cat > "$BUILD/usr/share/applications/voice-input.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Voice Input
Comment=全局语音输入 (SenseVoice)
Exec=/usr/bin/voice-input
Terminal=false
Categories=Utility;AudioVideo;
EOF

echo ">>> 写 DEBIAN/control"
INSTALLED_KB=$(du -sk "$BUILD/opt" | cut -f1)
cat > "$BUILD/DEBIAN/control" <<EOF
Package: voice-input
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: xdotool, xclip, libportaudio2
Installed-Size: $INSTALLED_KB
Maintainer: fnidore <fnidore@outlook.com>
Description: Voice Input - 全局语音输入工具
 按住快捷键说话，松开把识别结果输入到光标处。
 基于 SenseVoice + PySide6，支持中英文混说与自动标点。
 首次运行会自动下载 SenseVoice 模型（约 1GB）。
EOF

echo ">>> dpkg-deb 打包"
dpkg-deb --build --root-owner-group "$BUILD" "$PROJ/dist/$PKG.deb"
echo "✅ 生成: $PROJ/dist/$PKG.deb"
dpkg-deb --info "$PROJ/dist/$PKG.deb" | head -15
