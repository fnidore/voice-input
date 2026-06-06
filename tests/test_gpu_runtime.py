"""GPU 运行时模块测试：状态判断、启动激活、下载-解压-落盘全流程（mock 网络）。"""

import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import gpu_runtime  # noqa: E402


@pytest.fixture()
def runtime_dir(tmp_path, monkeypatch):
    """把运行时目录指到临时目录，避免污染真实用户数据。"""
    d = tmp_path / "gpu-runtime"
    monkeypatch.setattr(gpu_runtime, "GPU_RUNTIME_DIR", d)
    monkeypatch.setattr(gpu_runtime, "STATE_FILE", d / "installed.json")
    # 固定平台为 linux，让下载/解压测试在任意 CI runner（含无 GPU 的 macOS）一致
    monkeypatch.setattr(gpu_runtime, "_platform_key", lambda: "linux")
    return d


def _write_state(d: Path, version: str, completed: bool = True) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "installed.json").write_text(
        json.dumps({"version": version, "completed": completed}), encoding="utf-8")


def _make_fake_wheel(path: Path, pkg: str) -> dict:
    """构造一个最小轮子 zip，返回 manifest 条目。"""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"{pkg}/__init__.py", f'"""fake {pkg}"""\n')
    import hashlib
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"name": path.name, "size": path.stat().st_size, "sha256": sha}


class TestState:
    def test_not_installed_when_no_state(self, runtime_dir):
        assert not gpu_runtime.is_installed()

    def test_installed_with_valid_state(self, runtime_dir):
        _write_state(runtime_dir, gpu_runtime.RUNTIME_VERSION)
        assert gpu_runtime.is_installed()

    def test_version_mismatch_not_installed(self, runtime_dir):
        _write_state(runtime_dir, "9.9.9+cu999")
        assert not gpu_runtime.is_installed()

    def test_incomplete_not_installed(self, runtime_dir):
        _write_state(runtime_dir, gpu_runtime.RUNTIME_VERSION, completed=False)
        assert not gpu_runtime.is_installed()


class TestActivate:
    def test_no_runtime_no_activate(self, runtime_dir):
        assert gpu_runtime.activate() is False
        assert str(runtime_dir) not in sys.path

    def test_activate_prepends_sys_path(self, runtime_dir, monkeypatch):
        _write_state(runtime_dir, gpu_runtime.RUNTIME_VERSION)
        (runtime_dir / "torch").mkdir(parents=True)
        monkeypatch.setattr(sys, "path", list(sys.path))
        assert gpu_runtime.activate() is True
        assert sys.path[0] == str(runtime_dir)

    def test_state_ok_but_torch_dir_missing(self, runtime_dir, monkeypatch):
        _write_state(runtime_dir, gpu_runtime.RUNTIME_VERSION)
        monkeypatch.setattr(sys, "path", list(sys.path))
        assert gpu_runtime.activate() is False


class TestDownloadFlow:
    def test_full_install_flow(self, runtime_dir, tmp_path, monkeypatch):
        """mock 掉网络下载，验证 解压 + 删轮子 + 写状态 全链路。"""
        src = tmp_path / "src"
        src.mkdir()
        infos = [
            _make_fake_wheel(src / "torch-fake.whl", "torch"),
            _make_fake_wheel(src / "nvidia_fake.whl", "nvidia"),
        ]
        monkeypatch.setattr(gpu_runtime, "_FILES",
                            {"win": infos, "linux": infos})

        def fake_download(info, dest, base, total, cb, cancel):
            dest.write_bytes((src / info["name"]).read_bytes())

        monkeypatch.setattr(gpu_runtime, "_download_one", fake_download)
        progress = []
        gpu_runtime.download_runtime(
            progress_cb=lambda d, t, n: progress.append((d, t, n)))

        assert (runtime_dir / "torch" / "__init__.py").exists()
        assert (runtime_dir / "nvidia" / "__init__.py").exists()
        assert not list(runtime_dir.glob("*.whl")), "解压后轮子应删除"
        assert gpu_runtime.is_installed()
        assert progress and progress[-1][0] == progress[-1][1]

    def test_cancel_raises_and_not_installed(self, runtime_dir, tmp_path, monkeypatch):
        src = tmp_path / "src"
        src.mkdir()
        infos = [_make_fake_wheel(src / "torch-fake.whl", "torch")]
        monkeypatch.setattr(gpu_runtime, "_FILES", {"win": infos, "linux": infos})
        monkeypatch.setattr(
            gpu_runtime, "_download_one",
            lambda info, dest, base, total, cb, cancel:
            dest.write_bytes((src / info["name"]).read_bytes()))
        with pytest.raises(InterruptedError):
            gpu_runtime.download_runtime(cancel=lambda: True)
        assert not gpu_runtime.is_installed()

    def test_remove_runtime(self, runtime_dir):
        _write_state(runtime_dir, gpu_runtime.RUNTIME_VERSION)
        gpu_runtime.remove_runtime()
        assert not runtime_dir.exists()
        assert not gpu_runtime.is_installed()

    def test_empty_platform_raises(self, runtime_dir, monkeypatch):
        monkeypatch.setattr(gpu_runtime, "_FILES", {"win": [], "linux": []})
        with pytest.raises(RuntimeError):
            gpu_runtime.download_runtime()


class TestCandidateUrls:
    def test_order_aliyun_explicit_official(self, monkeypatch):
        monkeypatch.setattr(gpu_runtime, "_FLAT_MIRRORS",
                            ["https://aliyun/{q}", "https://official/{q}"])
        urls = gpu_runtime._candidate_urls(
            {"name": "x.whl", "urls": ["https://tsinghua/x.whl"]})
        assert urls == ["https://aliyun/x.whl",
                        "https://tsinghua/x.whl",
                        "https://official/x.whl"]

    def test_no_explicit_urls(self, monkeypatch):
        monkeypatch.setattr(gpu_runtime, "_FLAT_MIRRORS",
                            ["https://aliyun/{q}", "https://official/{q}"])
        urls = gpu_runtime._candidate_urls({"name": "y.whl"})
        assert urls == ["https://aliyun/y.whl", "https://official/y.whl"]

    def test_real_manifest_complete(self):
        """发版护栏：每个轮子都有非空 name/size/sha256。"""
        for plat in ("win", "linux"):
            assert gpu_runtime._FILES[plat], plat
            for f in gpu_runtime._FILES[plat]:
                assert f["name"].endswith(".whl")
                assert f["size"] > 0, f["name"]
                assert len(f["sha256"]) == 64, f["name"]

    def test_total_size_exceeds_int32(self):
        """护栏：运行时总量 >2^31，进度信号/进度条必须用 float/64 位，
        否则字节数会溢出 32 位 int 把进度条算崩（见 settings_window._gpuProgress）。"""
        INT32_MAX = 2 ** 31 - 1
        for plat in ("win", "linux"):
            total = sum(f["size"] for f in gpu_runtime._FILES[plat])
            assert total > INT32_MAX, f"{plat} total {total} 不再超 int32？重新评估进度信号类型"


class TestShaVerify:
    def test_mirror_fallback_on_bad_sha(self, runtime_dir, tmp_path, monkeypatch):
        """第一个镜像给坏文件 → 校验失败换下一个镜像成功。"""
        runtime_dir.mkdir(parents=True)
        good = tmp_path / "good.whl"
        info = _make_fake_wheel(good, "torch")

        served = []

        class FakeResp:
            def __init__(self, data):
                self._data = data

            def read(self, _n):
                d, self._data = self._data, b""
                return d

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=0):
            url = req.full_url
            served.append(url)
            if "mirror-bad" in url:
                return FakeResp(b"x" * info["size"])  # 大小对但内容错 → sha 失败
            return FakeResp(good.read_bytes())

        monkeypatch.setattr(gpu_runtime, "_FLAT_MIRRORS",
                            ["https://mirror-bad/{q}", "https://mirror-good/{q}"])
        monkeypatch.setattr(gpu_runtime.urllib.request, "urlopen", fake_urlopen)

        dest = runtime_dir / info["name"]
        gpu_runtime._download_one(info, dest, 0, info["size"], None, None)
        assert dest.exists()
        assert len(served) == 2 and "mirror-good" in served[1]
