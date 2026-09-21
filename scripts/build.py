"""构建脚本 — 下载 FFmpeg + PyInstaller 打包。"""
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
APP_NAME = "MediaDownloader"

# ── FFmpeg 下载 ──
FFMPEG_LINUX_URL = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
FFMPEG_WIN_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def download_file(url: str, dest: Path):
    """下载文件并显示进度。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  下载: {url.split('/')[-1]}")
    def progress(block, block_size, total_size):
        done = block * block_size
        pct = done * 100 // total_size if total_size else 0
        print(f"\r  进度: {pct}%", end="", flush=True)
    urllib.request.urlretrieve(url, str(dest), reporthook=progress)
    print()


def setup_linux_ffmpeg():
    """下载 Linux 静态 FFmpeg。"""
    print("\n=== 下载 Linux FFmpeg ===")
    archive = BUILD_DIR / "ffmpeg-linux.tar.xz"
    if not archive.exists():
        download_file(FFMPEG_LINUX_URL, archive)
    # 解压
    print("  解压...")
    subprocess.run(["tar", "xf", str(archive), "-C", str(BUILD_DIR)], check=True)
    # 找到 ffmpeg 二进制
    for f in BUILD_DIR.rglob("ffmpeg"):
        if f.is_file():
            dest = BUILD_DIR / "ffmpeg"
            shutil.copy2(f, dest)
            dest.chmod(0o755)
            print(f"  ✓ FFmpeg: {dest}")
            return dest
    raise FileNotFoundError("FFmpeg binary not found in archive")


def setup_windows_ffmpeg():
    """下载 Windows 静态 FFmpeg。"""
    print("\n=== 下载 Windows FFmpeg ===")
    archive = BUILD_DIR / "ffmpeg-win.zip"
    if not archive.exists():
        download_file(FFMPEG_WIN_URL, archive)
    print("  解压...")
    import zipfile
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if name.endswith("ffmpeg.exe"):
                with zf.open(name) as src, open(BUILD_DIR / "ffmpeg.exe", "wb") as dst:
                    dst.write(src.read())
                print(f"  ✓ FFmpeg: {BUILD_DIR / 'ffmpeg.exe'}")
                return BUILD_DIR / "ffmpeg.exe"
    raise FileNotFoundError("ffmpeg.exe not found in archive")


def build_linux():
    """构建 Linux 可执行文件。"""
    print("\n=== 构建 Linux ===")
    ffmpeg = setup_linux_ffmpeg()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--add-data", f"{ffmpeg}:.",
        "--add-data", f"{ROOT / 'ui' / 'gui' / 'resources' / 'styles.qss'}:ui/gui/resources",
        "--hidden-import", "curl_cffi",
        "--hidden-import", "PySide6",
        "--hidden-import", "qrcode",
        "--hidden-import", "PIL",
        str(ROOT / "main.py"),
    ]
    print(f"  命令: {' '.join(cmd[-3:])}")
    subprocess.run(cmd, check=True)
    print(f"  ✓ 构建完成: {DIST_DIR / APP_NAME}")


def build_windows():
    """构建 Windows 可执行文件。"""
    print("\n=== 构建 Windows ===")
    ffmpeg = setup_windows_ffmpeg()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--add-data", f"{ffmpeg};.",
        "--add-data", f"{ROOT / 'ui' / 'gui' / 'resources' / 'styles.qss'};ui/gui/resources",
        "--hidden-import", "curl_cffi",
        "--hidden-import", "PySide6",
        "--hidden-import", "qrcode",
        "--hidden-import", "PIL",
        str(ROOT / "main.py"),
    ]
    print(f"  命令: {' '.join(cmd[-3:])}")
    subprocess.run(cmd, check=True)
    print(f"  ✓ 构建完成: {DIST_DIR / (APP_NAME + '.exe')}")


def main():
    print(f"MediaDownloader 构建工具")
    print(f"平台: {platform.system()}")
    BUILD_DIR.mkdir(exist_ok=True)
    DIST_DIR.mkdir(exist_ok=True)

    # 先确认 PyInstaller 可用
    try:
        import PyInstaller
        print(f"PyInstaller: {PyInstaller.__version__}")
    except ImportError:
        print("安装 PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    if platform.system() == "Linux":
        build_linux()
    elif platform.system() == "Windows":
        build_windows()
    else:
        print(f"不支持的平台: {platform.system()}")
        return

    print("\n=== 构建完成 ===")
    for f in DIST_DIR.iterdir():
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"  {f.name}: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
