"""Douyin API client with encryption support."""
from __future__ import annotations
from json import dumps
from time import time as _time

from curl_cffi.requests import AsyncSession

from shared.core.constants import IMPERSONATE, USERAGENT, PARAMS_HEADERS
from shared.core.format import cookie_str_to_dict

from .encrypt import DouYinParams
from .encrypt.msToken import MsToken
from .encrypt.ttWid import TtWid


class DouyinAPI:
    """抖音 API 客户端 —— 自动处理加密签名 + msToken。"""

    API_DETAIL = "https://www.douyin.com/aweme/v1/web/aweme/detail/"

    BASE_PARAMS = {
        "device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web",
        "update_version_code": "170400", "pc_client_type": "1", "pc_libra_divert": "Mac",
        "support_h265": "1", "support_dash": "1", "version_code": "290100",
        "version_name": "29.1.0", "cookie_enabled": "true", "screen_width": "1536",
        "screen_height": "864", "browser_language": "zh-CN", "browser_platform": "MacIntel",
        "browser_name": "Chrome", "browser_version": "146.0.0.0", "browser_online": "true",
        "engine_name": "Blink", "engine_version": "146.0.0.0", "os_name": "Mac OS",
        "os_version": "10.15.7", "cpu_core_num": "16", "device_memory": "8",
        "platform": "PC", "downlink": "10", "effective_type": "4g",
        "round_trip_time": "200", "uifid": "", "msToken": "",
    }

    def __init__(self, cookie: str = "", proxy: str | None = None):
        self.cookie = cookie
        self.proxy = proxy
        self.ms_token = ""
        self.uifid = ""
        if cookie:
            d = cookie_str_to_dict(cookie)
            self.uifid = next((v for k, v in d.items() if k.lower() == "uifid"), "")

    def _build_headers(self) -> dict:
        h = PARAMS_HEADERS.copy()
        if self.cookie:
            h["Cookie"] = self.cookie
        if self.uifid:
            h["uifid"] = self.uifid
        return h

    async def update_ms_token(self) -> str:
        """从 mssdk 获取 msToken。"""
        try:
            headers = self._build_headers()
            ms_result = await _request_params(
                MsToken.API,
                data=dumps(MsToken.DATA | {"tspFromClient": int(_time() * 1000)}),
                headers=headers,
                params={MsToken.NAME: ""},
                proxy=self.proxy,
            )
            ms_data = TtWid.extract(None, ms_result, MsToken.NAME)
            self.ms_token = ms_data.get(MsToken.NAME, "") if ms_data else ""
            if self.ms_token:
                print(f"  msToken: {self.ms_token[:30]}...")
            return self.ms_token
        except Exception as e:
            print(f"  msToken error: {e}")
            return ""

    async def get_aweme_detail(self, aweme_id: str) -> dict | None:
        """获取单个作品详情。"""
        params_obj = DouYinParams()
        query = self.BASE_PARAMS | {"aweme_id": aweme_id, "msToken": ""}
        signed_query = params_obj.sign_url(
            self.API_DETAIL, query, method="GET", user_agent=USERAGENT,
        )
        url = f"{self.API_DETAIL}?{signed_query}"

        # 构建 headers（与测试通过的 test_debug.py 完全一致）
        h = PARAMS_HEADERS.copy()
        h["Cookie"] = self.cookie
        h["uifid"] = self.uifid

        async with AsyncSession(impersonate=IMPERSONATE) as client:
            resp = await client.get(url, headers=h, proxy=self.proxy)
            if resp.status_code == 200:
                return resp.json()
            print(f"  API error: HTTP {resp.status_code} - {resp.text[:200]}")
            return None

    async def close(self):
        pass


async def _request_params(url, data="", headers=None, params=None, proxy=None):
    """简化版 request_params（直接用 AsyncSession）。"""
    async with AsyncSession(impersonate=IMPERSONATE, verify=False) as client:
        resp = await client.post(url, data=data, headers=headers or {}, params=params or {}, proxy=proxy)
        resp.raise_for_status()
        return resp.headers
