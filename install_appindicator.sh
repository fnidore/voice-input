#!/usr/bin/env bash
# 装 GNOME AppIndicator 扩展，让 Voice Input 显示在顶栏托盘里
# 用法: bash install_appindicator.sh
#
# 注意: 安装完需要【注销重登】GNOME 才能加载扩展（GNOME 42/Ubuntu 22.04 限制）

set -e

echo "=================================================================="
echo "  Voice Input - GNOME AppIndicator 扩展安装器"
echo "=================================================================="

# 1. 检查 GNOME
if ! command -v gnome-shell >/dev/null 2>&1; then
  echo "[fatal] 检测不到 gnome-shell，你的桌面环境可能不是 GNOME"
  echo "        XFCE/KDE/Cinnamon 都原生支持托盘，不用装扩展"
  exit 1
fi

echo ""
echo "[1/4] GNOME 版本:"
gnome-shell --version

# 2. 装扩展包
echo ""
echo "[2/4] 安装 gnome-shell-extension-appindicator (需要 sudo) ..."
sudo apt update -qq
sudo apt install -y gnome-shell-extension-appindicator

# 3. 启用扩展
echo ""
echo "[3/4] 启用扩展 ..."
EXT_ID="appindicatorsupport@rgcjonas.gmail.com"

if gnome-extensions list 2>/dev/null | grep -q "$EXT_ID"; then
  gnome-extensions enable "$EXT_ID" 2>/dev/null || \
    echo "[warn] 现在启用失败（GNOME Shell 还没加载扩展），重登后会自动可用"
  echo "[ok] 扩展 $EXT_ID 已标记为启用"
else
  echo "[hint] 当前会话还看不到扩展，需要重登 GNOME 后才会注册"
fi

# 4. 提示重登
echo ""
echo "[4/4] 完成！请按下面任一方法重登 GNOME（必须！）："
echo ""
echo "  方法 A: 图形化注销 → 重新登录"
echo "  方法 B: 命令行: gnome-session-quit --logout"
echo ""
echo "重登后:"
echo "  1. 跑: gnome-extensions enable $EXT_ID  （如果没自动启用）"
echo "  2. 重启 voice-input:  systemctl --user restart voice-input.service"
echo "  3. 看顶栏右上角应该有 Voice Input 麦克风图标了"
echo ""
echo "=================================================================="
