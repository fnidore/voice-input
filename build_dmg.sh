#!/usr/bin/env bash
# 把 PyInstaller 产物 dist/Voice Input.app 打成 .dmg 磁盘映像。
# 用法: bash build_dmg.sh [版本号]   默认 0.1.0
# 依赖: 仅用 macOS 自带 hdiutil，无需 brew/create-dmg。
set -euo pipefail

VERSION="${1:-0.1.0}"
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$PROJ/dist/Voice Input.app"
DMG="$PROJ/dist/voice-input-${VERSION}.dmg"
STAGE="$PROJ/build/dmg"

if [ ! -d "$APP" ]; then
    echo "❌ 未找到 $APP，请先运行: pyinstaller voice_input.spec"
    exit 1
fi

echo ">>> 准备 dmg 暂存目录（含 /Applications 软链，方便拖拽安装）"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

echo ">>> hdiutil 生成压缩 dmg"
hdiutil create \
    -volname "Voice Input" \
    -srcfolder "$STAGE" \
    -ov \
    -format UDZO \
    "$DMG"

echo "✅ 生成: $DMG"
ls -lh "$DMG"
