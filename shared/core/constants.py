"""跨平台共享常量定义。"""
import sys
from pathlib import Path

# ======================== 路径 ========================

# _MEIPASS = PyInstaller 临时解压目录（用于读取捆绑资源如 ffmpeg、qss）
_MEIPASS: Path = Path(getattr(sys, "_MEIPASS", ""))

# ROOT = 可执行文件所在目录（数据存储位置）
# 注意：不能用 sys.executable，因为 onefile 模式下可能指向临时目录
if getattr(sys, "frozen", False):
    # PyInstaller onefile: 用 sys.argv[0] 获取真实可执行文件路径
    ROOT = Path(sys.argv[0]).resolve().parent
    if not ROOT.exists():
        ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent.parent

VOLUME: Path = ROOT / "Volume"
VOLUME.mkdir(exist_ok=True)

# ======================== 版本 ========================

VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_BETA = True
__VERSION__ = f"{VERSION_MAJOR}.{VERSION_MINOR}.{'beta' if VERSION_BETA else 'stable'}"
PROJECT_NAME = f"MediaDownloader V{VERSION_MAJOR}.{VERSION_MINOR} {'Beta' if VERSION_BETA else 'Stable'}"

# ======================== 链接 ========================

REPOSITORY = "https://github.com/npznnz/MediaDownloader"
DOCUMENTATION_URL = f"{REPOSITORY}/wiki/Documentation"
RELEASES = f"{REPOSITORY}/releases/latest"
LICENCE = "GNU General Public License v3.0"

# ======================== 网络 ========================

RETRY = 5
TIMEOUT = 10
MAX_WORKERS = 4
IMPERSONATE = "chrome146"

USERAGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)

# ======================== 颜色 (Rich) ========================

MASTER = "b #fff200"
PROMPT = "b turquoise2"
GENERAL = "b bright_white"
PROGRESS = "b bright_magenta"
ERROR = "b bright_red"
WARNING = "b bright_yellow"
INFO = "b bright_green"
DEBUG = "b dark_orange"

# ======================== Headers ========================

REFERER = "https://www.douyin.com/?recommend=1"
REFERER_TIKTOK = "https://www.tiktok.com/explore"

PARAMS_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "*/*",
    "Content-Type": "text/plain;charset=UTF-8",
    "Referer": REFERER,
}
PARAMS_HEADERS_TIKTOK = PARAMS_HEADERS | {
    "Referer": REFERER_TIKTOK,
}
DATA_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "*/*",
    "Referer": REFERER,
}
DATA_HEADERS_TIKTOK = DATA_HEADERS | {
    "Referer": REFERER_TIKTOK,
}
DOWNLOAD_HEADERS = {
    "Accept": "*/*",
    "Range": "bytes=0-",
    "Referer": REFERER,
}
DOWNLOAD_HEADERS_TIKTOK = DOWNLOAD_HEADERS | {
    "Referer": REFERER_TIKTOK,
}

# ======================== 文件签名 ========================

FILE_SIGNATURES: tuple[tuple[int, bytes, str], ...] = (
    (0, b"\xff\xd8\xff", "jpg"),
    (0, b"\x89PNG\r\n\x1a\n", "png"),
    (4, b"ftypavif", "avif"),
    (4, b"ftypheic", "heic"),
    (8, b"WEBP", "webp"),
    (4, b"ftypMSNV", "mp4"),
    (4, b"ftypisom", "mp4"),
    (4, b"ftypmp42", "m4v"),
    (4, b"ftypqt  ", "mov"),
    (0, b"\x1aE\xdf\xa3", "mkv"),
    (0, b"\x00\x00\x01\xb3", "mpg"),
    (0, b"\x00\x00\x01\xba", "mpg"),
    (0, b"FLV\x01", "flv"),
    (8, b"AVI ", "avi"),
)
FILE_SIGNATURES_LENGTH = max(
    offset + len(signature) for offset, signature, _ in FILE_SIGNATURES
)

# ======================== 免责声明 ========================

DISCLAIMER_TEXT = (
    "关于 MediaDownloader 的免责声明：\n"
    "\n"
    "1. 使用者对本项目的使用由使用者自行决定，并自行承担风险。\n"
    "2. 本项目提供的代码和功能基于现有知识和技术开发，不保证完全没有错误。\n"
    "3. 使用者需自行遵守相关法律法规，确保使用行为合法合规。\n"
    "4. 本项目不对使用者的数据收集、存储、传输等处理活动的合规性承担责任。\n"
    "5. 基于本项目的任何二次开发与原创作者无关。\n"
    "\n"
    "使用本项目即视为您已完全理解并接受以上免责声明。\n"
)
