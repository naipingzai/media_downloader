"""HTTP 会话工厂。"""
from __future__ import annotations

import os
from typing import Optional

from curl_cffi.requests import AsyncSession, Session

from .constants import IMPERSONATE, TIMEOUT, USERAGENT

__all__ = ["create_async_client", "create_sync_client", "request_params"]

# SSL 验证开关: 默认开启 (安全)。
# 仅在明确设置 MD_SSL_VERIFY=0 时关闭 (调试自签名代理场景)。
_SSL_VERIFY = os.environ.get("MD_SSL_VERIFY", "1") not in ("0", "false", "False")


def create_async_client(
    cookie: str | dict = "",
    proxy: Optional[str] = None,
    timeout: int = TIMEOUT,
    impersonate: str = IMPERSONATE,
    **kwargs,
) -> AsyncSession:
    """创建异步 HTTP 客户端。"""
    from .format import cookie_str_to_dict
    cookies = cookie_str_to_dict(cookie) if isinstance(cookie, str) else (cookie or {})
    return AsyncSession(
        timeout=timeout,
        verify=_SSL_VERIFY,
        allow_redirects=True,
        proxy=proxy,
        impersonate=impersonate,
        cookies=cookies,
        **kwargs,
    )


def create_sync_client(
    cookie: str | dict = "",
    proxy: Optional[str] = None,
    timeout: int = TIMEOUT,
    impersonate: str = IMPERSONATE,
    **kwargs,
) -> Session:
    """创建同步 HTTP 客户端。"""
    from .format import cookie_str_to_dict
    cookies = cookie_str_to_dict(cookie) if isinstance(cookie, str) else (cookie or {})
    return Session(
        timeout=timeout,
        verify=_SSL_VERIFY,
        allow_redirects=True,
        proxy=proxy,
        impersonate=impersonate,
        cookies=cookies,
        **kwargs,
    )


async def request_params(
    logger=None,
    url: str = "",
    method: str = "POST",
    params: dict | str = "",
    data: dict | str = "",
    useragent: str = USERAGENT,
    timeout: int = TIMEOUT,
    headers: dict | None = None,
    resp: str = "headers",
    proxy: str | None = None,
    impersonate: str = IMPERSONATE,
    **kwargs,
):
    """通用 HTTP 请求函数（兼容原项目 request_params 接口）。"""
    _headers = headers or {
        "Content-Type": "application/json; charset=utf-8",
    }
    with Session(
        headers=_headers,
        allow_redirects=True,
        timeout=timeout,
        verify=_SSL_VERIFY,
        proxy=proxy,
        impersonate=impersonate,
    ) as client:
        response = client.request(method, url, params=params, data=data, **kwargs)
        response.raise_for_status()
        match resp:
            case "headers":
                return response.headers
            case "text":
                return response.text
            case "content":
                return response.content
            case "json":
                return response.json()
            case "url":
                return str(response.url)
            case "response":
                return response
            case _:
                return response.headers
