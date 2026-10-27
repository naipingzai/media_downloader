"""异步重试装饰器 —— 按异常类型分级退避。"""
from __future__ import annotations

import asyncio
from typing import Callable, Coroutine, TypeVar

from .error import AuthError, FatalError, RateLimitedError, RetryableError

__all__ = ["Retry"]

T = TypeVar("T")

# 不可重试异常: 明确失败, 重试只会浪费时间或加重风控
_NON_RETRYABLE = (FatalError, AuthError)


class Retry:
    """可复用的重试控制，支持指数退避 + 异常分级。

    - FatalError / AuthError: 立即抛出, 不重试
    - RateLimitedError: 退避时间翻倍 (max_delay 至少 10s)
    - 其他异常 (网络/超时): 正常指数退避
    """

    def __init__(self, max_retry: int = 5, base_delay: float = 1.0,
                 max_delay: float = 30.0):
        self.max_retry = max_retry
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def run(
        self,
        func: Callable[..., Coroutine],
        *args,
        on_error: Callable[[Exception, int], None] | None = None,
        **kwargs,
    ):
        """执行异步函数，失败时自动重试。"""
        last_error = None
        for attempt in range(self.max_retry + 1):
            try:
                return await func(*args, **kwargs)
            except _NON_RETRYABLE:
                raise
            except RateLimitedError as e:
                last_error = e
                if on_error:
                    on_error(e, attempt + 1)
                if attempt < self.max_retry:
                    delay = min(self.base_delay * (2 ** attempt) * 2,
                                max(self.max_delay, 10.0))
                    await asyncio.sleep(delay)
            except RetryableError as e:
                last_error = e
                if on_error:
                    on_error(e, attempt + 1)
                if attempt < self.max_retry:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    await asyncio.sleep(delay)
            except Exception as e:
                # 未知异常按普通重试处理 (兼容旧逻辑, 不改变外部行为)
                last_error = e
                if on_error:
                    on_error(e, attempt + 1)
                if attempt < self.max_retry:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    await asyncio.sleep(delay)
        raise last_error
