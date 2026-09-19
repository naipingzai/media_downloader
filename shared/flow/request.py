"""Step 2: API 请求 —— 构建参数 + 加密签名 + 调用接口。"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from curl_cffi.requests import AsyncSession

__all__ = ["APIRequester"]


class APIRequester:
    """统一的 API 请求层。

    各平台适配器继承此类并实现:
    - build_params(): 构建请求参数
    - sign_request(): 加密签名
    - get_api_url(): API端点地址
    """

    def __init__(self, client: AsyncSession, cookie: str = "", proxy: str | None = None):
        self.client = client
        self.cookie = cookie
        self.proxy = proxy
        self.timeout = 10
        self.max_retry = 5

    async def get(self, url: str, headers: dict = None, **kwargs) -> dict | str:
        """GET 请求，自动重试。"""
        from ..core.retry import Retry
        retry = Retry(self.max_retry)
        return await retry.run(
            self._do_get, url, headers or {}, **kwargs,
            on_error=self._log_error,
        )

    async def post(self, url: str, data: dict = None, headers: dict = None, **kwargs) -> dict | str:
        """POST 请求，自动重试。"""
        from ..core.retry import Retry
        retry = Retry(self.max_retry)
        return await retry.run(
            self._do_post, url, data or {}, headers or {}, **kwargs,
            on_error=self._log_error,
        )

    async def _do_get(self, url: str, headers: dict, **kwargs) -> Any:
        from curl_cffi.requests.exceptions import RequestException
        try:
            resp = await self.client.get(url, headers=headers, proxy=self.proxy, **kwargs)
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return resp.text
        except RequestException as e:
            raise

    async def _do_post(self, url: str, data: dict, headers: dict, **kwargs) -> Any:
        from curl_cffi.requests.exceptions import RequestException
        try:
            resp = await self.client.post(url, json=data, headers=headers, proxy=self.proxy, **kwargs)
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return resp.text
        except RequestException as e:
            raise

    def _log_error(self, error: Exception, attempt: int):
        from ..core.constants import ERROR
        print(f"[重试 {attempt}] 请求失败: {error}")
