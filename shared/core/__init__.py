"""核心模块统一入口。"""
from .adapter import PlatformAdapter, PlatformConfig, DownloadResult
from .constants import (
    ROOT, VOLUME, _MEIPASS, VERSION_MAJOR, VERSION_MINOR, VERSION_BETA,
    __VERSION__, PROJECT_NAME, REPOSITORY, LICENCE, RELEASES,
    DOCUMENTATION_URL, DISCLAIMER_TEXT, IMPERSONATE, USERAGENT,
    MASTER, PROMPT, GENERAL, PROGRESS, ERROR, WARNING, INFO, DEBUG,
    REFERER, REFERER_TIKTOK,
    PARAMS_HEADERS, PARAMS_HEADERS_TIKTOK,
    DATA_HEADERS, DATA_HEADERS_TIKTOK,
    DOWNLOAD_HEADERS, DOWNLOAD_HEADERS_TIKTOK,
)
from .retry import Retry
from .session import create_async_client, create_sync_client
from .format import cookie_str_to_dict, cookie_dict_to_str
from .error import DownloaderError, CacheError
from .ffmpeg import FFmpegManager
from .cookies import CookieManager
from .login import LoginBus, PlatformLoginManager
from .config import AppConfig, ConfigManager
from .i18n import t as i18n_t, platform_name, PLATFORM_NAMES
from .ops import FeatureMeta, FeatureResult, PlatformBus, PlatformOps
from .adapter import norm_work, norm_user, norm_comment

__all__ = [
    "PlatformAdapter", "PlatformConfig", "DownloadResult",
    "ROOT", "VOLUME", "_MEIPASS", "VERSION_MAJOR", "VERSION_MINOR", "VERSION_BETA",
    "__VERSION__", "PROJECT_NAME", "REPOSITORY", "LICENCE", "RELEASES",
    "DOCUMENTATION_URL", "DISCLAIMER_TEXT", "IMPERSONATE",
    "MASTER", "PROMPT", "GENERAL", "PROGRESS", "ERROR", "WARNING", "INFO", "DEBUG",
    "Retry",
    "create_async_client", "create_sync_client",
    "cookie_str_to_dict", "cookie_dict_to_str",
    "DownloaderError", "CacheError",
    "FFmpegManager", "CookieManager", "LoginBus", "PlatformLoginManager",
    "AppConfig", "ConfigManager",
    "i18n_t", "platform_name", "PLATFORM_NAMES",
    "FeatureMeta", "FeatureResult", "PlatformBus", "PlatformOps",
    "norm_work", "norm_user", "norm_comment",
]
