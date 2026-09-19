"""异步重试装饰器。"""
from asyncio import sleep
from typing import Callable, Coroutine, TypeVar

__all__ = ["Retry"]

T = TypeVar("T")


class Retry:
    """可复用的重试控制，支持指数退避。"""

    def __init__(self, max_retry: int = 5, base_delay: float = 1.0, max_delay: float = 30.0):
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
            except Exception as e:
                last_error = e
                if on_error:
                    on_error(e, attempt + 1)
                if attempt < self.max_retry:
                    delay = min(self.base_delay * (2**attempt), self.max_delay)
                    await sleep(delay)
        raise last_error
