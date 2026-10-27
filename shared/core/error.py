"""自定义异常 —— 分层设计。

层级: 平台层(platforms/*) 捕获 RuntimeError 统一转 FeatureResult;
      以下异常按可重试性分类, 供 Retry 模块决策。
"""
from __future__ import annotations

__all__ = [
    "DownloaderError",
    "RetryableError",
    "FatalError",
    "RateLimitedError",
    "AuthError",
    "CacheError",
]


class DownloaderError(Exception):
    """下载器核心异常基类。"""


class RetryableError(DownloaderError):
    """可重试错误: 网络超时、连接失败、5xx 等。"""


class RateLimitedError(RetryableError):
    """触发平台风控/限流 (429 或业务码)。重试需更长退避。"""


class AuthError(DownloaderError):
    """认证失败: Cookie 过期/无效、需要登录。不应重试。"""


class FatalError(DownloaderError):
    """不可恢复错误: 参数错误、签名失败、接口结构变更。不应重试。"""


class CacheError(DownloaderError):
    """缓存操作异常。"""
