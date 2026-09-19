"""Kuaishou platform adapter - real API."""
from json import dumps
from shared.core import (
    PlatformAdapter, PlatformConfig, DownloadResult,
    create_async_client, PARAMS_HEADERS, USERAGENT, IMPERSONATE,
)
from shared.core.format import cookie_str_to_dict
from shared.translation import _
from .. import register_platform

@register_platform("kuaishou")
class KuaishouAdapter(PlatformAdapter):
    DOMAINS = ["kuaishou.com"]
    DISPLAY_NAME = "Kuaishou"
    API_DETAIL = "https://live.kuaishou.com/live_api/profile/feedbyid"
    API_USER = "https://www.kuaishou.com/rest/v/profile/feed"

    def __init__(self, config: PlatformConfig | None = None, **kwargs):
        self.config = config or PlatformConfig(name="kuaishou", display_name=self.DISPLAY_NAME, domains=self.DOMAINS, **kwargs)
        self.cookie = self.config.cookie
        self.proxy = self.config.proxy

    def get_config_schema(self) -> dict:
        return {"cookie": {"type": "str", "label": "Cookie"}, "proxy": {"type": "str", "label": "Proxy"}}

    async def extract_links(self, url: str) -> list[str]:
        from re import compile
        patterns = [compile(r"https?://(?:www\.)?kuaishou\.com/\S+"), compile(r"https?://v\.kuaishou\.com/\S+")]
        return [u for p in patterns for u in p.findall(url)]

    async def request_detail(self, link) -> dict | None:
        from curl_cffi.requests import AsyncSession
        work_id = link.work_id if hasattr(link, "work_id") else ""
        if not work_id: return None
        h = PARAMS_HEADERS.copy()
        h["Cookie"] = self.cookie
        h["Referer"] = "https://live.kuaishou.com"
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            r = await c.post(self.API_DETAIL, headers=h, data=dumps({"photoId": work_id, "principalId": ""}), timeout=10, proxy=self.proxy)
            if r.status_code == 200: return r.json()
            return None

    def parse_detail(self, raw: dict) -> dict | None:
        data = raw.get("data", {}).get("currentWork") if isinstance(raw, dict) else None
        if not data: return None
        return {
            "platform": "kuaishou", "work_id": data.get("photoId", ""),
            "title": data.get("caption", ""),
            "author_name": data.get("userName", ""),
            "author_id": data.get("userId", ""),
            "video_url": data.get("mainMvUrl", ""),
            "digg_count": data.get("likeCount", 0),
            "comment_count": data.get("commentCount", 0),
        }

    def get_download_urls(self, work: dict) -> list[str]:
        url = work.get("video_url", "")
        return [url] if url else []

    async def get_account_works(self, user_id: str, pages: int = 0) -> list[dict]: return []
    async def close(self): pass
