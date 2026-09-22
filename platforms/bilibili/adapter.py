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
PAGELIST_URL = "https://api.bilibili.com/x/player/pagelist"


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
        self.last_quality = ""   # 最近一次 fetch_playurl 实际拿到的清晰度描述
        self.last_low = False    # 最近一次是否低于 1080P（未登录/SESSDATA失效会被限制）

    def get_config_schema(self) -> dict:
        return {"cookie": {"type": "str", "label": "SESSDATA"}, "proxy": {"type": "str", "label": "Proxy"}}

    async def extract_links(self, url: str) -> list[str]:
        from re import compile
        patterns = [
            compile(r"https?://(?:www\.)?bilibili\.com/video/[A-Za-z0-9]+"),
            compile(r"https?://b23\.tv/[A-Za-z0-9]+"),
        ]
        return [u for p in patterns for u in p.findall(url)]

    def _headers(self) -> dict:
        """构造统一请求头。

        SESSDATA 容错：配置可能存的是纯值（xxx）、带前缀（SESSDATA=xxx）
        或从浏览器复制的整串 Cookie（a=1; SESSDATA=xx; ...），均正确处理。
        """
        h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
        raw = (self.cookie or "").strip()
        if raw:
            if "=" in raw:
                from shared.core.format import cookie_str_to_dict
                ck = cookie_str_to_dict(raw)
                if ck:
                    h["Cookie"] = "; ".join(f"{k}={v}" for k, v in ck.items())
                else:
                    h["Cookie"] = f"SESSDATA={raw}"
            else:
                h["Cookie"] = f"SESSDATA={raw}"
        return h

    async def _ensure_wbi(self, client):
        if self._img_key and self._sub_key:
            return
        h = self._headers()
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
            h = self._headers()
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
        """返回空列表，实际下载地址通过 fetch_playurl 获取。"""
        return []

    async def get_account_works(self, user_id: str, pages: int = 0) -> list[dict]:
        """委托给 fetch_user_videos。"""
        return await self.fetch_user_videos(user_id, max_count=pages or 30)

    async def close(self):
        """无需清理资源。"""
        pass

    # ── 扩展 API 方法 ──

    @staticmethod
    def _sj(resp):
        """safe json"""
        try:
            d = resp.json()
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _jget(d, *keys):
        """safe chained dict.get"""
        for k in keys:
            if not isinstance(d, dict):
                return None
            d = d.get(k)
        return d

    async def fetch_playurl(self, bvid: str) -> list[str]:
        """获取视频下载地址。"""
        if not bvid:
            return []
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                await self._ensure_wbi(c)
                params = {"bvid": bvid}
                if self._img_key and self._sub_key:
                    params = _wbi_sign(params, self._img_key, self._sub_key)
                h = self._headers()
                r = await c.get(VIEW_URL, params=params, headers=h, proxy=self.proxy)
                if r.status_code != 200:
                    return []
                data = self._sj(r)
                if data.get("code") != 0:
                    return []
                cid = self._jget(data, "data", "cid")
                if not cid:
                    return []
                play_params = {
                    "bvid": bvid, "cid": cid,
                    "qn": "120", "fnval": "4048", "fourk": "1",
                }
                if self._img_key and self._sub_key:
                    play_params = _wbi_sign(play_params, self._img_key, self._sub_key)
                r2 = await c.get(PLAYURL_URL, params=play_params, headers=h, proxy=self.proxy)
                if r2.status_code != 200:
                    return []
                pdata = self._jget(self._sj(r2), "data") or {}
                fmts = {f.get("quality"): (f.get("new_description") or f.get("description") or "")
                        for f in (pdata.get("support_formats") or [])}
                dash = pdata.get("dash")
                if dash:
                    video_list = dash.get("video") or []
                    audio_list = dash.get("audio") or []
                    if video_list:
                        # 按清晰度 id 分组取最高档（id 即 qn：16=360P 32=480P 64=720P
                        # 80=1080P 112=1080P+ 116=1080P60 120=4K 125=HDR 126=杜比）
                        best_id = max(v.get("id") or 0 for v in video_list)
                        top = [v for v in video_list if (v.get("id") or 0) == best_id]
                        def _rank(v):
                            c = (v.get("codecs") or "").lower()
                            cr = 0 if c.startswith("avc1") else (1 if c.startswith(("hev", "hvc")) else 2)
                            return (cr, -(v.get("bandwidth") or 0))
                        best_video = min(top, key=_rank)
                        self.last_quality = fmts.get(best_id) or f"qn={best_id}"
                        self.last_low = best_id < 80
                        urls = [best_video.get("baseUrl") or best_video.get("base_url") or ""]
                        if audio_list:
                            best_audio = max(audio_list, key=lambda x: ((x.get("id") or 0), (x.get("bandwidth") or 0)))
                            urls.append(best_audio.get("baseUrl") or best_audio.get("base_url") or "")
                        return [u for u in urls if u]
                durl = pdata.get("durl")
                if durl:
                    qn = pdata.get("quality") or 0
                    self.last_quality = fmts.get(qn) or (f"qn={qn}" if qn else "")
                    self.last_low = 0 < int(qn) < 80
                    return [d.get("url", "") for d in durl if d.get("url")]
                return []
        except Exception:
            return []

    async def fetch_user_videos(self, mid: str, max_count: int = 30) -> list[dict]:
        """获取用户视频列表。"""
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                await self._ensure_wbi(c)
                h = self._headers()
                videos = []
                pn = 1
                while len(videos) < max_count:
                    params = {"mid": mid, "ps": "30", "pn": str(pn), "order": "pubdate"}
                    if self._img_key and self._sub_key:
                        params = _wbi_sign(params, self._img_key, self._sub_key)
                    url = f"{BASE_URL}/x/space/wbi/arc/search"
                    r = await c.get(url, params=params, headers=h, proxy=self.proxy)
                    if r.status_code != 200:
                        break
                    data = self._sj(r)
                    vlist = self._jget(data, "data", "list", "vlist") or []
                    if not vlist:
                        break
                    videos.extend(vlist)
                    total = self._jget(data, "data", "page", "count") or 0
                    if len(videos) >= total or len(videos) >= max_count:
                        break
                    pn += 1
                return videos[:max_count]
        except Exception:
            return []

    async def fetch_series_list(self, mid: str) -> list[dict]:
        """获取用户的合集/系列列表。"""
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                await self._ensure_wbi(c)
                h = self._headers()
                params = {"mid": mid, "ps": "20", "pn": "1"}
                if self._img_key and self._sub_key:
                    params = _wbi_sign(params, self._img_key, self._sub_key)
                url = f"{BASE_URL}/x/polymer/web-space/seasons_series_list"
                r = await c.get(url, params=params, headers=h, proxy=self.proxy)
                if r.status_code != 200:
                    return []
                items = self._jget(self._sj(r), "data", "items_lists") or {}
                seasons = items.get("seasons_list") or []
                series = items.get("series_list") or []
                result = []
                for s in seasons:
                    meta = s.get("meta", {})
                    meta["type"] = "season"
                    result.append({"meta": meta})
                for s in series:
                    meta = s.get("meta", {})
                    meta["type"] = "series"
                    result.append({"meta": meta})
                return result
        except Exception:
            return []

    async def fetch_series_archives(self, mid: str, sid: int) -> list[dict]:
        """获取合集/系列视频列表。"""
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                await self._ensure_wbi(c)
                h = self._headers()
                params = {"mid": mid, "series_id": str(sid), "ps": "30", "pn": "1"}
                if self._img_key and self._sub_key:
                    params = _wbi_sign(params, self._img_key, self._sub_key)
                r = await c.get(SERIES_URL, params=params, headers=h, proxy=self.proxy)
                if r.status_code != 200:
                    return []
                return self._jget(self._sj(r), "data", "archives") or []
        except Exception:
            return []

    async def fetch_favorite_list(self, fid: str = "0") -> list[dict]:
        """获取收藏夹内容列表。"""
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                await self._ensure_wbi(c)
                h = self._headers()
                if fid == "0":
                    fav_params = {"up_mid": ""}
                    if self._img_key and self._sub_key:
                        fav_params = _wbi_sign(fav_params, self._img_key, self._sub_key)
                    r0 = await c.get(f"{BASE_URL}/x/v3/fav/folder/created/list-all",
                                     params=fav_params, headers=h, proxy=self.proxy)
                    if r0.status_code == 200:
                        folders = self._jget(self._sj(r0), "data", "list") or []
                        if folders:
                            fid = str(folders[0].get("id", "0"))
                all_items = []
                pn = 1
                while True:
                    params = {"media_id": fid, "pn": str(pn), "ps": "20", "order": "mtime"}
                    if self._img_key and self._sub_key:
                        params = _wbi_sign(params, self._img_key, self._sub_key)
                    r = await c.get(FAVORITE_URL, params=params, headers=h, proxy=self.proxy)
                    if r.status_code != 200:
                        break
                    data = self._sj(r)
                    medias = self._jget(data, "data", "medias") or []
                    if not medias:
                        break
                    all_items.extend(medias)
                    if not data.get("data", {}).get("has_more", False):
                        break
                    pn += 1
                return all_items
        except Exception:
            return []

    async def fetch_comments(self, bvid: str, cid: int, max_count: int = 50) -> list[dict]:
        """采集视频评论。"""
        try:
            from curl_cffi.requests import AsyncSession
            aid = 0
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                h = self._headers()
                params = {"bvid": bvid}
                if self._img_key and self._sub_key:
                    params = _wbi_sign(params, self._img_key, self._sub_key)
                r = await c.get(VIEW_URL, params=params, headers=h, proxy=self.proxy)
                if r.status_code == 200:
                    aid = self._jget(self._sj(r), "data", "aid") or 0
            if not aid:
                return []
            comments = []
            next_offset = ""
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                h = self._headers()
                while len(comments) < max_count:
                    url = f"{BASE_URL}/x/v2/reply/main"
                    params = {"oid": str(aid), "type": "1", "mode": "3"}
                    if next_offset:
                        params["next"] = next_offset
                    r = await c.get(url, params=params, headers=h, proxy=self.proxy)
                    if r.status_code != 200:
                        break
                    data = self._sj(r)
                    cursor = self._jget(data, "data", "cursor") or {}
                    replies = self._jget(data, "data", "replies") or []
                    if not replies:
                        break
                    comments.extend(replies)
                    next_offset = str(cursor.get("next", ""))
                    if not cursor.get("is_end", False):
                        continue
                    break
            return comments[:max_count]
        except Exception:
            return []

    async def fetch_cid(self, bvid: str) -> int:
        """获取视频第一个分P的cid。"""
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
                r = await c.get(f"{PAGELIST_URL}?bvid={bvid}", headers=h, proxy=self.proxy)
                if r.status_code == 200:
                    pages = self._sj(r)
                    plist = pages.get("data") or []
                    if plist and isinstance(plist, list):
                        return plist[0].get("cid", 0)
        except Exception:
            pass
        return 0

    async def fetch_user_info(self, mid: str) -> dict:
        """获取用户资料。"""
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                h = self._headers()
                params = {"mid": mid}
                if self._img_key and self._sub_key:
                    params = _wbi_sign(params, self._img_key, self._sub_key)
                r = await c.get(f"{BASE_URL}/x/web-interface/card", params=params, headers=h, proxy=self.proxy)
                if r.status_code != 200:
                    return {}
                card = self._jget(self._sj(r), "data", "card") or {}
                if not card:
                    return {}
                return {
                    "name": card.get("name", ""),
                    "fans": card.get("fans", 0),
                    "following": card.get("attention", 0),
                    "sign": card.get("sign", ""),
                    "level": card.get("level", 0),
                }
        except Exception:
            return {}
