"""自定义异常。"""

__all__ = ["DownloaderError", "CacheError"]


class DownloaderError(Exception):
    """下载器核心异常。"""
    pass


class CacheError(Exception):
    """缓存操作异常。"""
    pass
