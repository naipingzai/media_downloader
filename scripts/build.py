"""构建脚本 — 下载 FFmpeg + PyInstaller 打包。"""
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

FFMPEG_LINUX_URL = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
FFMPEG_WIN_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def download_file(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading: {url.split('/')[-1]}")
    urllib.request.urlretrieve(url, str(dest))
    print("  Done.")


def get_pyinstaller_cmd():
    """Build the PyInstaller command with all hidden imports."""
    is_win = platform.system() == "Windows"
    sep = ";" if is_win else ":"
    ffmpeg_name = "ffmpeg.exe" if is_win else "ffmpeg"
    ffmpeg_path = BUILD_DIR / ffmpeg_name
    qss_path = ROOT / "ui" / "gui" / "resources" / "styles.qss"
    check_svg = ROOT / "static" / "checkbox_check.svg"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--additional-hooks-dir", str(ROOT / "hooks"),
        f"--add-data", f"{ffmpeg_path}{sep}.",
        f"--add-data", f"{qss_path}{sep}ui/gui/resources",
        f"--add-data", f"{check_svg}{sep}static",
        # Core dependencies
        "--hidden-import", "curl_cffi",
        "--hidden-import", "curl_cffi._curl_cffi",
        "--hidden-import", "PySide6",
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "qrcode",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        # Platform modules
        "--hidden-import", "platforms",
        "--hidden-import", "platforms.douyin",
        "--hidden-import", "platforms.douyin.adapter",
        "--hidden-import", "platforms.douyin.ops",
        "--hidden-import", "platforms.douyin.login",
        "--hidden-import", "platforms.douyin.encrypt",
        "--hidden-import", "platforms.douyin.encrypt.douyin_params",
        "--hidden-import", "platforms.douyin.encrypt.websign",
        "--hidden-import", "platforms.kuaishou",
        "--hidden-import", "platforms.kuaishou.adapter",
        "--hidden-import", "platforms.kuaishou.ops",
        "--hidden-import", "platforms.kuaishou.login",
        "--hidden-import", "platforms.xiaohongshu",
        "--hidden-import", "platforms.xiaohongshu.adapter",
        "--hidden-import", "platforms.xiaohongshu.ops",
        "--hidden-import", "platforms.xiaohongshu.login",
        "--hidden-import", "platforms.bilibili",
        "--hidden-import", "platforms.bilibili.adapter",
        "--hidden-import", "platforms.bilibili.ops",
        "--hidden-import", "platforms.bilibili.login",
        # Shared modules
        "--hidden-import", "shared.core.ops",
        "--hidden-import", "shared.core.adapter",
        "--hidden-import", "shared.core.config",
        "--hidden-import", "shared.core.ffmpeg",
        "--hidden-import", "shared.core.cookies",
        "--hidden-import", "shared.core.session",
        "--hidden-import", "shared.core.storage",
        "--hidden-import", "shared.core.i18n",
        "--hidden-import", "shared.core.constants",
        "--hidden-import", "shared.core.format",
        "--hidden-import", "shared.flow.link",
        "--hidden-import", "shared.flow.download",
        "--hidden-import", "shared.core.login",
        "--hidden-import", "ui.gui.cover_loader",
        "--hidden-import", "ui.gui.widgets",
        "--hidden-import", "ui.gui.widgets.cover_label",
        "--hidden-import", "ui.gui.widgets.work_card",
        "--hidden-import", "ui.gui.widgets.video_info",
        "--hidden-import", "ui.gui.widgets.batch_preview",
        str(ROOT / "main.py"),
    ]
    return cmd


def setup_linux_ffmpeg():
    print("\n=== Downloading Linux FFmpeg ===")
    archive = BUILD_DIR / "ffmpeg-linux.tar.xz"
    if not archive.exists():
        download_file(FFMPEG_LINUX_URL, archive)
    print("  Extracting...")
    subprocess.run(["tar", "xf", str(archive), "-C", str(BUILD_DIR)], check=True)
    dest = BUILD_DIR / "ffmpeg"
    if dest.exists() and dest.is_file():
        dest.chmod(0o755)
        print(f"  FFmpeg (already exists): {dest}")
        return dest
    for f in BUILD_DIR.rglob("ffmpeg"):
        if f.is_file() and f != dest:
            shutil.copy2(f, dest)
            dest.chmod(0o755)
            print(f"  FFmpeg: {dest}")
            return dest
    raise FileNotFoundError("ffmpeg not found")


def setup_windows_ffmpeg():
    print("\n=== Downloading Windows FFmpeg ===")
    archive = BUILD_DIR / "ffmpeg-win.zip"
    if not archive.exists():
        download_file(FFMPEG_WIN_URL, archive)
    import zipfile
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if name.endswith("ffmpeg.exe"):
                with zf.open(name) as src, open(BUILD_DIR / "ffmpeg.exe", "wb") as dst:
                    dst.write(src.read())
                print(f"  FFmpeg: {BUILD_DIR / 'ffmpeg.exe'}")
                return BUILD_DIR / "ffmpeg.exe"
    raise FileNotFoundError("ffmpeg.exe not found")


def main():
    print(f"MediaDownloader Build - {platform.system()}")
    BUILD_DIR.mkdir(exist_ok=True)
    DIST_DIR.mkdir(exist_ok=True)

    if platform.system() == "Linux":
        setup_linux_ffmpeg()
    elif platform.system() == "Windows":
        setup_windows_ffmpeg()
    else:
        print(f"Unsupported: {platform.system()}")
        return

    cmd = get_pyinstaller_cmd()
    print(f"\nRunning PyInstaller...")
    subprocess.run(cmd, check=True)

    print("\n=== Build Complete ===")
    for f in DIST_DIR.iterdir():
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"  {f.name}: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
