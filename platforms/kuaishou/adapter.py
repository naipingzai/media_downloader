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

    async def fetch_user_videos(self, user_id: str, max_count: int = 30) -> list[dict]:
        """获取用户视频列表。"""
        from curl_cffi.requests import AsyncSession
        h = PARAMS_HEADERS.copy()
        h["Cookie"] = self.cookie
        h["Referer"] = "https://www.kuaishou.com"
        videos = []
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            pcursor = ""
            while len(videos) < max_count:
                payload = {"principalId": user_id, "pcursor": pcursor}
                r = await c.post(self.API_USER, headers=h, data=dumps(payload), timeout=10, proxy=self.proxy)
                if r.status_code != 200:
                    break
                data = r.json().get("data", {}).get("list") or []
                if not data:
                    break
                videos.extend(data)
                pcursor = r.json().get("data", {}).get("pcursor", "")
                if not pcursor or pcursor == "no_more":
                    break
        return videos[:max_count]

    async def close(self): pass

    # ===== 统一扩展接口 =====
    async def fetch_user_posts(self, sec_uid: str, count: int = 20, max_cursor: str = "0"):
        from shared.core.adapter import norm_work
        videos = await self.fetch_user_videos(sec_uid, max_count=max(count, 30))
        return [norm_work(v, "kuaishou") for v in videos]

    async def fetch_current_user(self):
        """获取当前登录快手用户 (从 /rest/v/profile/info 拉取)。"""
        from shared.core.adapter import norm_user
        try:
            from curl_cffi.requests import AsyncSession
            h = PARAMS_HEADERS.copy()
            h["Cookie"] = self.cookie
            h["Referer"] = "https://www.kuaishou.com"
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                r = await c.get("https://www.kuaishou.com/rest/v/profile/info",
                                headers=h, proxy=self.proxy, timeout=10)
                if r.status_code != 200:
                    return None
                d = r.json().get("data") or {}
                if not d:
                    return None
                return norm_user({
                    "userId": d.get("userId") or d.get("principalId", ""),
                    "nickname": d.get("userName") or d.get("nickname", ""),
                    "avatar": d.get("headUrl") or d.get("avatar", ""),
                    "signature": d.get("userText") or "",
                    "follower_count": d.get("fansCount", 0),
                    "following_count": d.get("followCount", 0),
                    "aweme_count": d.get("photoCount", 0),
                }, "kuaishou")
        except Exception:
            return None

    async def fetch_user_profile(self, sec_uid: str):
        """拉取作者资料 (从 /rest/v/profile/otherInfo 拉取)。"""
        from shared.core.adapter import norm_user
        try:
            from curl_cffi.requests import AsyncSession
            h = PARAMS_HEADERS.copy()
            h["Cookie"] = self.cookie
            h["Referer"] = "https://www.kuaishou.com"
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                r = await c.get("https://www.kuaishou.com/rest/v/profile/otherInfo",
                                params={"principalId": sec_uid},
                                headers=h, proxy=self.proxy, timeout=10)
                if r.status_code != 200:
                    return norm_user({"userId": sec_uid, "nickname": sec_uid,
                                      "platform": "kuaishou"}, "kuaishou")
                d = r.json().get("data") or {}
                return norm_user({
                    "userId": d.get("userId") or sec_uid,
                    "nickname": d.get("userName") or d.get("nickname", sec_uid),
                    "avatar": d.get("headUrl") or d.get("avatar", ""),
                    "signature": d.get("userText") or "",
                    "follower_count": d.get("fansCount", 0),
                    "following_count": d.get("followCount", 0),
                    "aweme_count": d.get("photoCount", 0),
                }, "kuaishou")
        except Exception:
            return norm_user({"userId": sec_uid, "nickname": sec_uid,
                              "platform": "kuaishou"}, "kuaishou")

    async def fetch_collection(self, cursor: str = "0", count: int = 20):
        """拉取收藏作品 (从 /rest/v/feed/collection 获取)。"""
        from shared.core.adapter import norm_work
        try:
            from curl_cffi.requests import AsyncSession
            h = PARAMS_HEADERS.copy()
            h["Cookie"] = self.cookie
            h["Referer"] = "https://www.kuaishou.com"
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                pcursor = cursor or ""
                items = []
                while len(items) < count:
                    r = await c.get("https://www.kuaishou.com/rest/v/feed/collection",
                                    params={"pcursor": pcursor},
                                    headers=h, proxy=self.proxy, timeout=10)
                    if r.status_code != 200:
                        break
                    data = r.json().get("data") or {}
                    feeds = data.get("list") or []
                    if not feeds:
                        break
                    items.extend(feeds)
                    pcursor = data.get("pcursor", "")
                    if not pcursor or pcursor == "no_more":
                        break
                return [norm_work(w, "kuaishou") for w in items[:count]]
        except Exception:
            return None

    async def fetch_user_following(self, sec_uid: str, count: int = 20, max_time: str = "0"):
        """拉取关注列表 (从 /rest/v/relation/following 获取)。"""
        from shared.core.adapter import norm_user
        try:
            from curl_cffi.requests import AsyncSession
            h = PARAMS_HEADERS.copy()
            h["Cookie"] = self.cookie
            h["Referer"] = "https://www.kuaishou.com"
            users, pcursor = [], ""
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                while len(users) < count:
                    r = await c.get("https://www.kuaishou.com/rest/v/relation/following",
                                    params={"principalId": sec_uid, "pcursor": pcursor},
                                    headers=h, proxy=self.proxy, timeout=10)
                    if r.status_code != 200:
                        break
                    data = r.json().get("data") or {}
                    lst = data.get("list") or []
                    if not lst:
                        break
                    for u in lst:
                        users.append(norm_user(u, "kuaishou"))
                    pcursor = data.get("pcursor", "")
                    if not pcursor or pcursor == "no_more":
                        break
                return {"followings": users[:count], "has_more": False} if users else None
        except Exception:
            return None

