# Voice Input - Windows 一键安装 (PowerShell)
# 用法: powershell -ExecutionPolicy Bypass -File install_windows.ps1

$ErrorActionPreference = "Stop"
Write-Host "===== Voice Input Windows 安装 =====" -ForegroundColor Cyan

# 1. 检查 Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Error "未找到 python，请先安装 Python 3.10+ (https://www.python.org/downloads/)"
    exit 1
}
$ver = (python -c "import sys;print('%d.%d' % sys.version_info[:2])")
Write-Host "检测到 Python $ver"

# 2. 创建虚拟环境
$proj = $PSScriptRoot
$venv = Join-Path $proj ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "创建虚拟环境 .venv ..."
    python -m venv $venv
}
$pyExe = Join-Path $venv "Scripts\python.exe"

# 3. 升级 pip + 安装项目依赖
Write-Host "安装依赖 (requirements.txt) ..." -ForegroundColor Yellow
& $pyExe -m pip install --upgrade pip
& $pyExe -m pip install -r (Join-Path $proj "requirements.txt")

# 4. 安装 PyTorch (默认 CPU 版)
Write-Host "安装 PyTorch (CPU 版) ..." -ForegroundColor Yellow
& $pyExe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
Write-Host "如需 N 卡 GPU 加速，请到 https://pytorch.org 选对应 CUDA 版重装 torch" -ForegroundColor DarkGray

# 5. 完成提示
$gui = Join-Path $proj "voice_input_gui.py"
Write-Host "`n✅ 安装完成!" -ForegroundColor Green
Write-Host "启动命令:" -ForegroundColor Green
Write-Host "  `"$pyExe`" `"$gui`""
Write-Host "`n提示: 首次运行会自动下载 ~1GB SenseVoice 模型，请耐心等待。" -ForegroundColor DarkGray
