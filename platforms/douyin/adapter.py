"""Douyin/TikTok platform adapter — all APIs."""
from shared.core import (
    PlatformAdapter, PlatformConfig, DownloadResult,
    PARAMS_HEADERS, USERAGENT, IMPERSONATE, VOLUME,
)
from shared.core.format import cookie_str_to_dict
from .. import register_platform


@register_platform("douyin")
class DouyinAdapter(PlatformAdapter):
    DOMAINS = ["douyin.com", "tiktok.com"]
    DISPLAY_NAME = "Douyin / TikTok"

    def __init__(self, config: PlatformConfig | None = None, **kwargs):
        self.config = config or PlatformConfig(
            name="douyin", display_name=self.DISPLAY_NAME,
            domains=self.DOMAINS, **kwargs,
        )
        self.cookie = self.config.cookie
        self.proxy = self.config.proxy
        d = cookie_str_to_dict(self.cookie)
        self.uifid = next((v for k, v in d.items() if k.lower() == "uifid"), "")
        if not self.uifid:
            import uuid
            self.uifid = str(uuid.uuid4())

    def get_config_schema(self) -> dict:
        return {"cookie": {"type": "str", "label": "Cookie"}, "proxy": {"type": "str", "label": "Proxy"}}

    async def extract_links(self, url: str) -> list[str]:
        from re import compile
        return [u for p in [compile(r"https?://(?:www\.)?douyin\.com/\S+"), compile(r"https?://v\.douyin\.com/\S+"), compile(r"https?://(?:www\.)?tiktok\.com/\S+")] for u in p.findall(url)]

    # ---- common signed request ----
    async def _signed_get(self, api_url: str, extra_params: dict) -> dict | None:
        from curl_cffi.requests import AsyncSession
        from platforms.douyin.encrypt import DouYinParams
        p = DouYinParams()
        q = self._base_params() | extra_params
        signed = p.sign_url(api_url, q, method="GET", user_agent=USERAGENT)
        h = PARAMS_HEADERS.copy()
        h["Cookie"] = self.cookie
        h["uifid"] = self.uifid
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            r = await c.get(f"{api_url}?{signed}", headers=h, proxy=self.proxy)
            if r.status_code != 200:
                return None
            try:
                return r.json()
            except Exception:
                return None

    # ---- detail ----
    async def request_detail(self, link) -> dict | None:
        work_id = link.work_id if hasattr(link, "work_id") else ""
        if not work_id: return None
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/aweme/detail/", {"uifid": self.uifid, "msToken": "", "aweme_id": work_id})

    def parse_detail(self, raw: dict) -> dict | None:
        aweme = raw.get("aweme_detail") if isinstance(raw, dict) else None
        if not aweme: return None
        video = aweme.get("video", {})
        play = video.get("play_addr", {}).get("url_list", [])
        bit_rate = video.get("bit_rate", [])
        if bit_rate:
            best = max(bit_rate, key=lambda x: x.get("bit_rate", 0))
            play = best.get("play_addr", {}).get("url_list", []) or play
        author = aweme.get("author", {})
        return {
            "platform": "douyin", "work_id": aweme.get("aweme_id", ""),
            "title": aweme.get("desc", ""),
            "author_name": author.get("nickname", ""),
            "author_id": author.get("uid", ""),
            "sec_user_id": author.get("sec_uid", ""),
            "video_url": play[0] if play else "",
            "share_url": f"https://www.douyin.com/video/{aweme.get("aweme_id", "")}",
            "digg_count": aweme.get("statistics", {}).get("digg_count", 0),
            "comment_count": aweme.get("statistics", {}).get("comment_count", 0),
        }

    def get_download_urls(self, work: dict) -> list[str]:
        url = work.get("video_url", "")
        return [url] if url else []

    async def get_account_works(self, user_id: str, pages: int = 0) -> list[dict]:
        return []

    # ---- user posts ----
    async def fetch_user_posts(self, sec_user_id: str, count: int = 20, max_cursor: str = "0") -> dict | None:
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/aweme/post/", {"sec_user_id": sec_user_id, "count": str(count), "max_cursor": max_cursor, "uifid": self.uifid, "msToken": ""})

    # ---- user profile ----
    async def fetch_user_profile(self, sec_user_id: str) -> dict | None:
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/user/profile/other/", {"sec_user_id": sec_user_id})

    # ---- comments ----
    async def fetch_comments(self, aweme_id: str, cursor: int = 0, count: int = 20) -> dict | None:
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/comment/list/", {"aweme_id": aweme_id, "cursor": str(cursor), "count": str(count), "item_type": "0"})

    # ---- mix (collection of works) ----
    async def fetch_mix(self, mix_id: str, count: int = 20, cursor: int = 0) -> dict | None:
        # 受保护接口必须携带 uifid 才会生成 WebSign，否则 403 Signature Not Found
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/mix/aweme/", {"mix_id": mix_id, "count": str(count), "cursor": str(cursor), "uifid": self.uifid, "msToken": ""})

    # ---- search ----
    async def fetch_search(self, keyword: str, offset: int = 0, count: int = 20) -> dict | None:
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/search/item/", {"keyword": keyword, "search_channel": "aweme_video_web", "search_source": "normal_search", "query_correct_type": "1", "is_filter_search": "0", "from_group_id": "", "offset": str(offset), "count": str(count), "search_id": ""})

    # ---- live ----
    async def fetch_live(self, room_id: str, room_id_str: str = "") -> dict | None:
        """抖音直播进房接口。

        room_id 为分享链接中的 web_rid（纯数字短号）；
        room_id_str 为长房间 ID（如 feed 接口返回的 id_str）。

        live.douyin.com 的 webcast API 必须携带 ttwid 会话 cookie，
        否则网关直接返回空 body (HTTP 200, content-length: 0)。
        因此先访问直播间页面建立会话，再合并用户 cookie 请求 API。
        """
        from curl_cffi.requests import AsyncSession
        from platforms.douyin.encrypt import DouYinParams
        api = "https://live.douyin.com/webcast/room/web/enter/"
        q = {
            "aid": "6383", "app_name": "douyin_web", "live_id": "1",
            "device_platform": "web", "language": "zh-CN",
            "browser_language": "zh-CN", "browser_platform": "Win32",
            "browser_name": "Chrome", "browser_version": "146.0.0.0",
            "web_rid": "" if room_id_str else room_id,
            "room_id_str": room_id_str,
            "enter_from": "", "page_from": "", "enter_source": "",
            "is_need_double_stream": "false",
            "cookie_enabled": "true", "screen_width": "1920",
            "screen_height": "1080", "channel": "channel_pc_web",
        }
        signed = DouYinParams().sign_url(api, q, method="GET", user_agent=USERAGENT)
        h = PARAMS_HEADERS.copy()
        h["Referer"] = f"https://live.douyin.com/{room_id}"
        h["Origin"] = "https://live.douyin.com"
        h["Accept"] = "application/json, text/plain, */*"
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            # 1) 预热会话 — 获取 ttwid / UIFID
            warm_h = {"User-Agent": USERAGENT,
                      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
            if self.cookie:
                warm_h["Cookie"] = self.cookie
            await c.get(f"https://live.douyin.com/{room_id}",
                        headers=warm_h, proxy=self.proxy)
            # 2) 合并用户 cookie 与会话 cookie（同名后者覆盖）
            jar = "; ".join(f"{k}={v}" for k, v in c.cookies.items())
            merged: dict[str, str] = {}
            for part in (self.cookie, jar):
                for kv in part.split(";"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        merged[k.strip()] = v.strip()
            if merged:
                h["Cookie"] = "; ".join(f"{k}={v}" for k, v in merged.items())
            # 3) 请求进房接口
            r = await c.get(f"{api}?{signed}", headers=h, proxy=self.proxy)
            if r.status_code != 200 or not r.content:
                return None
            try:
                return r.json()
            except Exception:
                return None

    # ---- collection / favorites ----
    async def fetch_collection(self, cursor: str = "0", count: int = 20) -> dict | None:
        """收藏的作品列表（需登录 Cookie）。type=1 为收藏的作品。"""
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/aweme/listcollection/", {"cursor": cursor, "count": str(count), "type": "1", "uifid": self.uifid, "msToken": ""})

    async def fetch_collection_albums(self, cursor: str = "0", count: int = 20) -> dict | None:
        """收藏的专辑（合集）列表（需登录 Cookie）。

        抖音「我的收藏 → 专辑」入口；探测确认 endpoint 存在
        （未登录返回 403 Argus 而非 404）。
        """
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/mix/listcollection/", {"cursor": cursor, "count": str(count), "uifid": self.uifid, "msToken": ""})

    async def fetch_favorites(self, cursor: str = "0", count: int = 20) -> dict | None:
        """喜欢的作品列表（需登录 Cookie）。"""
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/aweme/favorite/", {"cursor": cursor, "count": str(count), "sec_user_id": "", "mix_id": "", "uifid": self.uifid, "msToken": ""})

    # ---- hot ----
    async def fetch_hot_list(self) -> list[dict]:
        data = await self._signed_get("https://www.douyin.com/aweme/v1/web/hot/search/list/", {})
        if not data: return []
        wl = data.get("data", {}).get("word_list", [])
        return [{"rank": i + 1, "word": it.get("word", ""), "hot_value": it.get("hot_value", 0)} for i, it in enumerate(wl[:20])]

    async def close(self):
        pass

    def _base_params(self) -> dict:
        return {
            "device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web",
            "update_version_code": "170400", "pc_client_type": "1", "pc_libra_divert": "Mac",
            "support_h265": "1", "support_dash": "1", "version_code": "290100",
            "version_name": "29.1.0", "cookie_enabled": "true", "screen_width": "1536",
            "screen_height": "864", "browser_language": "zh-CN", "browser_platform": "MacIntel",
            "browser_name": "Chrome", "browser_version": "146.0.0.0", "browser_online": "true",
            "engine_name": "Blink", "engine_version": "146.0.0.0", "os_name": "Mac OS",
            "os_version": "10.15.7", "cpu_core_num": "16", "device_memory": "8",
            "platform": "PC", "downlink": "10", "effective_type": "4g",
            "round_trip_time": "200",
        }
