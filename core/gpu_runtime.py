"""GPU 加速运行时：按需下载 CUDA 版 torch，启动期插队加载。

安装包内置 CPU 版 torch（体积小、全员可用）；有 N 卡的用户在设置里
一键下载 CUDA 运行时（轮子解压到用户数据目录），重启后 sys.path 插队
盖过内置 CPU 版，识别走 GPU。

设计要点：
- 版本锁定：运行时 torch 版本必须与打包内置版本一致（CI 锁 2.11.0），
  2.11.0 是 Python 3.10 最后一个有 cu128 轮子的版本。
- Windows 一个大轮子全包 CUDA DLL；Linux 的 CUDA 库拆在 nvidia-* 轮子里，
  解压后与 site-packages 相对布局一致，torch 的 RPATH 能找到。
- 下载源带备链：阿里云 → alist 自建 → 官方，逐个重试，断点续传 + sha256 校验。
"""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import json
import logging
import os
import platform
import shutil
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from core.config import DATA_DIR

logger = logging.getLogger(__name__)

RUNTIME_VERSION = "2.11.0+cu128"
GPU_RUNTIME_DIR = DATA_DIR / "gpu-runtime"
STATE_FILE = GPU_RUNTIME_DIR / "installed.json"

# 扁平路径镜像（{q} = URL 编码的轮子文件名），按文件名直接拼接，顺序即优先级。
# 阿里云是纯国内 PyTorch wheel 镜像（torch/torchaudio + 大部分 nvidia 在此）；
# 官方源兜底。个别阿里云缺失的 nvidia 轮子在各 manifest 条目的 "urls" 里给清华
# PyPI 的内容寻址直链（清华路径不可由文件名推导，必须显式存）。
_FLAT_MIRRORS = [
    "https://mirrors.aliyun.com/pytorch-wheels/cu128/{q}",
    "https://download.pytorch.org/whl/cu128/{q}",
]


def _candidate_urls(info: dict) -> list[str]:
    """单个轮子的候选下载地址：阿里云扁平 → 显式备链（清华） → 官方扁平。"""
    q = urllib.parse.quote(info["name"])
    urls = [_FLAT_MIRRORS[0].format(q=q)]
    urls += info.get("urls", [])
    urls += [m.format(q=q) for m in _FLAT_MIRRORS[1:]]
    return urls


# 轮子清单（torch 2.11.0+cu128 / cp310；sha256 取自官方索引，size 实测核验）。
# Windows 轮子自带 CUDA DLL（单个 torch 2.6GB）；Linux 需 torch+torchaudio+15
# 个 nvidia-* 轮子（torch 经 RPATH $ORIGIN/../nvidia/*/lib 找 CUDA 库，须同目录）。
_FILES: dict[str, list[dict]] = {
    "win": [
        {"name": "torch-2.11.0+cu128-cp310-cp310-win_amd64.whl",
         "size": 2753152602, "sha256": "7c792fe95ad5edaf622cf9e4f5573f5aecf2bc0654c7e866eda6134088f95d72"},
        {"name": "torchaudio-2.11.0+cu128-cp310-cp310-win_amd64.whl",
         "size": 1671568, "sha256": "312af3435dc299b8f6e0aa07381a684565970f1b7086b8d07b2fd63f9b3eaeda"},
    ],
    "linux": [
        {"name": "torch-2.11.0+cu128-cp310-cp310-manylinux_2_28_x86_64.whl",
         "size": 820206653, "sha256": "72d53f3176a69cc20710c4ecb95f7dc4c6ba10c4e4eda45b8396ee79ee40f75a"},
        {"name": "torchaudio-2.11.0+cu128-cp310-cp310-manylinux_2_28_x86_64.whl",
         "size": 1684267, "sha256": "034fbae103061b74694eb1963a5e918749bca3c0e998ad5bd05125bcfe903122"},
        {"name": "nvidia_cublas_cu12-12.8.4.1-py3-none-manylinux_2_27_x86_64.whl",
         "size": 594346921, "sha256": "8ac4e771d5a348c551b2a426eda6193c19aa630236b418086020df5ba9667142"},
        {"name": "nvidia_cuda_cupti_cu12-12.8.90-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl",
         "size": 10248621, "sha256": "ea0cb07ebda26bb9b29ba82cda34849e73c166c18162d3913575b0c9db9a6182"},
        {"name": "nvidia_cuda_nvrtc_cu12-12.8.93-py3-none-manylinux2010_x86_64.manylinux_2_12_x86_64.whl",
         "size": 88040029, "sha256": "a7756528852ef889772a84c6cd89d41dfa74667e24cca16bb31f8f061e3e9994"},
        {"name": "nvidia_cuda_runtime_cu12-12.8.90-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl",
         "size": 954765, "sha256": "adade8dcbd0edf427b7204d480d6066d33902cab2a4707dcfc48a2d0fd44ab90"},
        {"name": "nvidia_cudnn_cu12-9.19.0.56-py3-none-manylinux_2_27_x86_64.whl",
         "size": 657906812, "sha256": "ac6ad90a075bb33a94f2b4cf4622eac13dd4dc65cf6dd9c7572a318516a36625",
         "urls": ["https://pypi.tuna.tsinghua.edu.cn/packages/c5/41/65225d42fba06fb3dd3972485ea258e7dd07a40d6e01c95da6766ad87354/nvidia_cudnn_cu12-9.19.0.56-py3-none-manylinux_2_27_x86_64.whl"]},
        {"name": "nvidia_cufft_cu12-11.3.3.83-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl",
         "size": 193118695, "sha256": "4d2dd21ec0b88cf61b62e6b43564355e5222e4a3fb394cac0db101f2dd0d4f74"},
        {"name": "nvidia_cufile_cu12-1.13.1.3-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl",
         "size": 1197834, "sha256": "1d069003be650e131b21c932ec3d8969c1715379251f8d23a1860554b1cb24fc"},
        {"name": "nvidia_curand_cu12-10.3.9.90-py3-none-manylinux_2_27_x86_64.whl",
         "size": 63619976, "sha256": "b32331d4f4df5d6eefa0554c565b626c7216f87a06a4f56fab27c3b68a830ec9"},
        {"name": "nvidia_cusolver_cu12-11.7.3.90-py3-none-manylinux_2_27_x86_64.whl",
         "size": 267506905, "sha256": "4376c11ad263152bd50ea295c05370360776f8c3427b30991df774f9fb26c450"},
        {"name": "nvidia_cusparse_cu12-12.5.8.93-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl",
         "size": 288216466, "sha256": "1ec05d76bbbd8b61b06a80e1eaf8cf4959c3d4ce8e711b65ebd0443bb0ebb13b"},
        {"name": "nvidia_cusparselt_cu12-0.7.1-py3-none-manylinux2014_x86_64.whl",
         "size": 287193691, "sha256": "f1bb701d6b930d5a7cea44c19ceb973311500847f81b634d802b7b539dc55623"},
        {"name": "nvidia_nccl_cu12-2.28.9-py3-none-manylinux_2_18_x86_64.whl",
         "size": 296782137, "sha256": "485776daa8447da5da39681af455aa3b2c2586ddcf4af8772495e7c532c7e5ab",
         "urls": ["https://pypi.tuna.tsinghua.edu.cn/packages/4a/4e/44dbb46b3d1b0ec61afda8e84837870f2f9ace33c564317d59b70bc19d3e/nvidia_nccl_cu12-2.28.9-py3-none-manylinux_2_18_x86_64.whl"]},
        {"name": "nvidia_nvjitlink_cu12-12.8.93-py3-none-manylinux2010_x86_64.manylinux_2_12_x86_64.whl",
         "size": 39254836, "sha256": "81ff63371a7ebd6e6451970684f916be2eab07321b73c9d244dc2b4da7f73b88"},
        {"name": "nvidia_nvshmem_cu12-3.4.5-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl",
         "size": 139103095, "sha256": "042f2500f24c021db8a06c5eec2539027d57460e1c1a762055a6554f72c369bd",
         "urls": ["https://pypi.tuna.tsinghua.edu.cn/packages/b5/09/6ea3ea725f82e1e76684f0708bbedd871fc96da89945adeba65c3835a64c/nvidia_nvshmem_cu12-3.4.5-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"]},
        {"name": "nvidia_nvtx_cu12-12.8.90-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl",
         "size": 89954, "sha256": "5b17e2001cc0d751a5bc2c6ec6d26ad95913324a4adb86788c944f8ce9ba441f"},
    ],
}

# 进度回调签名：cb(已完成字节, 总字节, 当前文件名)
ProgressCb = Callable[[int, int, str], None]


def _platform_key() -> str | None:
    """当前平台对应的清单 key；mac 无 CUDA 返回 None。"""
    if sys.platform.startswith("win"):
        return "win"
    if sys.platform.startswith("linux"):
        return "linux"
    return None


def files_for_platform() -> list[dict]:
    key = _platform_key()
    return _FILES.get(key, []) if key else []


def total_download_size() -> int:
    return sum(f["size"] for f in files_for_platform())


def detect_nvidia() -> bool:
    """有没有 N 卡驱动（nvidia-smi 随驱动安装，Win/Linux 通用）。"""
    return shutil.which("nvidia-smi") is not None


def is_installed() -> bool:
    """运行时是否完整安装（半截下载/解压不算）。"""
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return bool(state.get("completed")) and state.get("version") == RUNTIME_VERSION
    except Exception:
        return False


# torch 及其 CUDA 依赖的顶层包名——只对这些走外部运行时，其余仍用内置
_OVERRIDE_PREFIXES = ("torch", "torchaudio", "torio", "functorch", "torchgen",
                      "nvidia", "triton", "pytorch_triton")


class _ExternalRuntimeFinder(importlib.abc.MetaPathFinder):
    """拦截 torch 系包名，强制从 GPU 运行时目录加载。

    打包应用里 torch 的纯 Python 部分进了 PyInstaller 的 PYZ，由 FrozenImporter
    解析——它在 sys.meta_path 中优先级高于处理 sys.path 的 PathFinder，单靠
    sys.path.insert 盖不过内置 CPU 版。把本 finder 插到 meta_path 最前，
    对 torch.* 显式用 PathFinder 在运行时目录里找，即可让 GPU 版胜出。
    """

    def __init__(self, root: str) -> None:
        self.root = root

    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition(".")[0] not in _OVERRIDE_PREFIXES:
            return None
        # 顶层包用运行时目录；子模块沿用父包 __path__（已指向运行时目录）
        search = list(path) if path else [self.root]
        return importlib.machinery.PathFinder.find_spec(fullname, search, target)


def activate() -> bool:
    """启动期调用（必须在任何 torch import 之前）：插队加载 GPU 运行时。"""
    if not is_installed():
        return False
    if not (GPU_RUNTIME_DIR / "torch").is_dir():
        logger.warning("gpu runtime state ok but torch dir missing, skip activate")
        return False
    root = str(GPU_RUNTIME_DIR)
    if not is_active():
        sys.meta_path.insert(0, _ExternalRuntimeFinder(root))
        sys.path.insert(0, root)
        # Linux 上 torch 经 RPATH($ORIGIN/../nvidia/*/lib) 找 CUDA 库，nvidia
        # 包与 torch 同在运行时目录即可；Windows 轮子自带 DLL 在 torch/lib。
    logger.info("GPU runtime activated: %s", root)
    return True


def is_active() -> bool:
    return any(isinstance(f, _ExternalRuntimeFinder) for f in sys.meta_path)


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_one(info: dict, dest: Path, base_done: int, total: int,
                  progress_cb: ProgressCb | None,
                  cancel: Callable[[], bool] | None) -> None:
    """单文件下载：镜像逐个试，断点续传，完成后 sha256 校验。"""
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_err: Exception | None = None
    for url in _candidate_urls(info):
        try:
            pos = tmp.stat().st_size if tmp.exists() else 0
            if pos >= info["size"]:
                tmp.unlink()  # 异常残留，重下
                pos = 0
            req = urllib.request.Request(url, headers={"User-Agent": "voice-input"})
            if pos:
                req.add_header("Range", f"bytes={pos}-")
            with urllib.request.urlopen(req, timeout=60) as r, \
                    open(tmp, "ab" if pos else "wb") as f:
                while True:
                    if cancel and cancel():
                        raise InterruptedError("用户取消")
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    pos += len(chunk)
                    if progress_cb:
                        progress_cb(base_done + pos, total, info["name"])
            if tmp.stat().st_size != info["size"]:
                raise OSError(f"大小不符 {tmp.stat().st_size} != {info['size']}")
            sha = _sha256_of(tmp)
            if sha != info["sha256"]:
                tmp.unlink()  # 防被污染的镜像反复命中
                raise OSError(f"sha256 校验失败 {sha[:12]}")
            tmp.replace(dest)
            return
        except InterruptedError:
            raise
        except Exception as e:  # 网络/校验失败 → 换下一个镜像
            logger.warning("download %s from %s failed: %s", info["name"], url, e)
            last_err = e
    raise RuntimeError(f"{info['name']} 所有镜像均失败: {last_err}")


def _extract_wheel(whl: Path) -> None:
    """轮子就是 zip：解压进运行时目录（多个 nvidia 轮子共享 nvidia/ 目录，自动合并）。"""
    with zipfile.ZipFile(whl) as z:
        z.extractall(GPU_RUNTIME_DIR)


def download_runtime(progress_cb: ProgressCb | None = None,
                     cancel: Callable[[], bool] | None = None) -> None:
    """下载 + 解压全套运行时。失败抛异常；完成写 installed.json。

    progress_cb 跑在调用线程（应由 GUI 用信号桥转回主线程）。
    """
    files = files_for_platform()
    if not files:
        raise RuntimeError("当前平台没有可用的 GPU 运行时（仅支持 Windows/Linux + N 卡）")
    GPU_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.unlink(missing_ok=True)  # 重装前先标记为不完整

    total = sum(f["size"] for f in files)
    done = 0
    wheels: list[Path] = []
    for info in files:
        dest = GPU_RUNTIME_DIR / info["name"]
        if not (dest.exists() and dest.stat().st_size == info["size"]
                and _sha256_of(dest) == info["sha256"]):
            _download_one(info, dest, done, total, progress_cb, cancel)
        done += info["size"]
        if progress_cb:
            progress_cb(done, total, info["name"])
        wheels.append(dest)

    for whl in wheels:
        if cancel and cancel():
            raise InterruptedError("用户取消")
        logger.info("extracting %s", whl.name)
        _extract_wheel(whl)
        whl.unlink()  # 解压完删轮子省空间

    STATE_FILE.write_text(json.dumps({
        "version": RUNTIME_VERSION,
        "completed": True,
        "platform": _platform_key(),
        "machine": platform.machine(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("GPU runtime installed: %s", GPU_RUNTIME_DIR)


def remove_runtime() -> None:
    """删除运行时目录（释放约 6GB），重启后回到内置 CPU 版。"""
    shutil.rmtree(GPU_RUNTIME_DIR, ignore_errors=True)
    logger.info("GPU runtime removed")
