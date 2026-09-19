"""Bilibili platform adapter — 基于 bilibili-downloader 的 API。"""
import hashlib
import time
import urllib.parse
from typing import Optional
from shared.core import PlatformAdapter, PlatformConfig, PARAMS_HEADERS, USERAGENT, IMPERSONATE
from .. import register_platform

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

BASE_URL = "https://api.bilibili.com"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
PLAYURL_URL = "https://api.bilibili.com/x/player/playurl"
SERIES_URL = "https://api.bilibili.com/x/series/archives"
SEASON_URL = "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list"
FAVORITE_URL = "https://api.bilibili.com/x/v3/fav/resource/list"


def _wbi_sign(params: dict, img_key: str, sub_key: str) -> dict:
    mixin_key = (img_key + sub_key)
    mixin_key = "".join([mixin_key[i] for i in MIXIN_KEY_ENC_TAB])[:32]
    params["wts"] = str(int(time.time()))
    sorted_params = dict(sorted(params.items()))
    query = urllib.parse.urlencode(sorted_params)
    w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
    sorted_params["w_rid"] = w_rid
    return sorted_params


@register_platform("bilibili")
class BilibiliAdapter(PlatformAdapter):
    DOMAINS = ["bilibili.com", "b23.tv"]
    DISPLAY_NAME = "Bilibili"

    def __init__(self, config: PlatformConfig | None = None, **kwargs):
        self.config = config or PlatformConfig(name="bilibili", display_name=self.DISPLAY_NAME, domains=self.DOMAINS, **kwargs)
        self.cookie = self.config.cookie
        self.proxy = self.config.proxy
        self._img_key = ""
        self._sub_key = ""

    def get_config_schema(self) -> dict:
        return {"cookie": {"type": "str", "label": "SESSDATA"}, "proxy": {"type": "str", "label": "Proxy"}}

    async def extract_links(self, url: str) -> list[str]:
        from re import compile
        patterns = [
            compile(r"https?://(?:www\.)?bilibili\.com/video/[A-Za-z0-9]+"),
            compile(r"https?://b23\.tv/[A-Za-z0-9]+"),
        ]
        return [u for p in patterns for u in p.findall(url)]

    async def _ensure_wbi(self, client):
        if self._img_key and self._sub_key:
            return
        h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
        if self.cookie:
            h["Cookie"] = f"SESSDATA={self.cookie}"
        try:
            r = await client.get(NAV_URL, headers=h)
            data = r.json().get("data", {})
            wbi = data.get("wbi_img", {})
            img_url = wbi.get("img_url", "")
            sub_url = wbi.get("sub_url", "")
            self._img_key = img_url.split("/")[-1].split(".")[0] if img_url else ""
            self._sub_key = sub_url.split("/")[-1].split(".")[0] if sub_url else ""
        except Exception:
            pass

    async def request_detail(self, link) -> dict | None:
        from curl_cffi.requests import AsyncSession
        url = link.url if hasattr(link, "url") else str(link)
        bvid = ""
        from re import compile
        m = compile(r"bilibili\.com/video/([A-Za-z0-9]+)").search(url)
        if m:
            bvid = m.group(1)
        if not bvid:
            return None
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            await self._ensure_wbi(c)
            params = {"bvid": bvid}
            if self._img_key and self._sub_key:
                params = _wbi_sign(params, self._img_key, self._sub_key)
            h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
            if self.cookie:
                h["Cookie"] = f"SESSDATA={self.cookie}"
            r = await c.get(VIEW_URL, params=params, headers=h, proxy=self.proxy)
            if r.status_code == 200:
                data = r.json()
                if data.get("code") == 0:
                    return {"view": data.get("data", {}), "bvid": bvid}
            return None

    def parse_detail(self, raw: dict) -> dict | None:
        if not raw or "view" not in raw:
            return None
        v = raw["view"]
        owner = v.get("owner", {})
        stat = v.get("stat", {})
        return {
            "platform": "bilibili",
            "work_id": v.get("bvid", ""),
            "title": v.get("title", ""),
            "author_name": owner.get("name", ""),
            "author_id": str(owner.get("mid", "")),
            "video_url": "",
            "cover_url": v.get("pic", ""),
            "duration": v.get("duration", 0),
            "digg_count": stat.get("like", 0),
            "comment_count": stat.get("reply", 0),
            "view_count": stat.get("view", 0),
            "share_count": stat.get("share", 0),
        }

    def get_download_urls(self, work: dict) -> list[str]:
        return []

    async def get_account_works(self, user_id: str, pages: int = 0) -> list[dict]:
        return []

    async def close(self):
        pass
