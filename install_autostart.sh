#!/usr/bin/env bash
# 安装 systemd user service，让 Voice Input 开机自启
# 用法:
#   bash install_autostart.sh           # 安装并启用
#   bash install_autostart.sh disable   # 仅禁用（保留文件）
#   bash install_autostart.sh remove    # 禁用并删除 service 文件

set -e
cd "$(dirname "$0")"

SERVICE_NAME="voice-input.service"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/$SERVICE_NAME"
RUN_SCRIPT="$(pwd)/run_gui.sh"

write_service() {
  mkdir -p "$SERVICE_DIR"
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Voice Input (SenseVoice global voice dictation)
After=graphical-session.target sound.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/bin/bash $RUN_SCRIPT
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
  echo "[ok] 已写入 $SERVICE_FILE"
}

case "${1:-enable}" in
  enable)
    write_service
    systemctl --user daemon-reload
    systemctl --user enable --now "$SERVICE_NAME"
    echo "[ok] 开机自启已启用，并已启动服务"
    echo "[hint] 查看状态: systemctl --user status $SERVICE_NAME"
    echo "[hint] 查看日志: journalctl --user -u $SERVICE_NAME -f"
    ;;
  disable)
    systemctl --user disable --now "$SERVICE_NAME" || true
    echo "[ok] 已禁用开机自启（service 文件保留）"
    ;;
  remove)
    systemctl --user disable --now "$SERVICE_NAME" || true
    rm -f "$SERVICE_FILE"
    systemctl --user daemon-reload
    echo "[ok] 已禁用并删除 service 文件"
    ;;
  *)
    echo "用法: $0 [enable|disable|remove]"
    exit 1
    ;;
esac
