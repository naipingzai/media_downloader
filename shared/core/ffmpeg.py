"""FFmpeg detection and command builder — 支持系统/内置 FFmpeg。"""
import logging
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _bundled_candidates() -> list[Path]:
    """PyInstaller 冻结后查找内置 FFmpeg。"""
    if not getattr(sys, "frozen", False):
        return []
    exe_name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    exe_dir = Path(sys.executable).resolve().parent
    candidates = [exe_dir / exe_name]
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / exe_name)
    return candidates


class FFmpegManager:
    """定位 FFmpeg 并构建合并/转码命令。"""

    @staticmethod
    def find_executable(custom_path: Optional[str] = None) -> Optional[Path]:
        if custom_path:
            p = Path(custom_path)
            if p.is_file():
                return p
        # 优先查找内置 FFmpeg
        for bp in _bundled_candidates():
            if bp.is_file():
                return bp
        # 查找系统 FFmpeg
        found = shutil.which("ffmpeg")
        if found:
            return Path(found)
        # 常见路径
        search = [
            Path("/usr/bin/ffmpeg"),
            Path("/usr/local/bin/ffmpeg"),
            Path.home() / "ffmpeg" / "bin" / "ffmpeg",
        ]
        for p in search:
            if p.is_file():
                return p
        return None

    @classmethod
    def check_available(cls, custom_path: Optional[str] = None) -> tuple[bool, str]:
        exe = cls.find_executable(custom_path)
        if not exe:
            return False, "FFmpeg 未找到，请在设置中配置路径"
        try:
            r = subprocess.run(
                [str(exe), "-version"], capture_output=True, text=True, timeout=5
            )
            version = r.stdout.split("\n")[0] if r.stdout else str(exe)
            return True, version
        except Exception as e:
            return False, f"FFmpeg 检测失败: {e}"

    @staticmethod
    def build_merge_command(
        video: str, audio: str, output: str, codec: str = "copy"
    ) -> list[str]:
        exe = FFmpegManager.find_executable()
        if not exe:
            return []
        return [
            str(exe), "-y",
            "-i", video, "-i", audio,
            "-c:v", codec, "-c:a", "aac",
            "-strict", "experimental",
            output,
        ]

    @staticmethod
    def build_convert_command(
        input_path: str, output_path: str, fmt: str = "mp4"
    ) -> list[str]:
        exe = FFmpegManager.find_executable()
        if not exe:
            return []
        return [
            str(exe), "-y",
            "-i", input_path,
            "-c:v", "copy", "-c:a", "copy",
            output_path,
        ]

    @staticmethod
    def run_command(cmd: list[str], timeout: int = 300) -> tuple[bool, str]:
        if not cmd:
            return False, "FFmpeg 未配置"
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            if r.returncode == 0:
                return True, r.stdout
            return False, r.stderr[:500] if r.stderr else "未知错误"
        except subprocess.TimeoutExpired:
            return False, "FFmpeg 执行超时"
        except Exception as e:
            return False, str(e)
