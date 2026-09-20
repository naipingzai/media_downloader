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

    # ── 扩展 API 方法 ──

    async def fetch_playurl(self, bvid: str) -> list[str]:
        """获取视频下载地址。"""
        if not bvid:
            return []
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            await self._ensure_wbi(c)
            # 先获取 cid
            params = {"bvid": bvid}
            if self._img_key and self._sub_key:
                params = _wbi_sign(params, self._img_key, self._sub_key)
            h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
            if self.cookie:
                h["Cookie"] = f"SESSDATA={self.cookie}"
            r = await c.get(VIEW_URL, params=params, headers=h, proxy=self.proxy)
            if r.status_code != 200:
                return []
            data = r.json()
            if data.get("code") != 0:
                return []
            cid = data["data"].get("cid", 0)
            if not cid:
                return []
            # 获取 playurl
            play_params = {
                "bvid": bvid, "cid": cid,
                "qn": "80", "fnval": "16", "fourk": "1",
            }
            if self._img_key and self._sub_key:
                play_params = _wbi_sign(play_params, self._img_key, self._sub_key)
            r2 = await c.get(PLAYURL_URL, params=play_params, headers=h, proxy=self.proxy)
            if r2.status_code != 200:
                return []
            pdata = r2.json().get("data", {})
            # DASH 格式
            dash = pdata.get("dash")
            if dash:
                video_list = dash.get("video", [])
                audio_list = dash.get("audio", [])
                if video_list:
                    # 选最高质量
                    best_video = max(video_list, key=lambda x: x.get("bandwidth", 0))
                    urls = [best_video.get("baseUrl", "") or best_video.get("base_url", "")]
                    if audio_list:
                        best_audio = max(audio_list, key=lambda x: x.get("bandwidth", 0))
                        urls.append(best_audio.get("baseUrl", "") or best_audio.get("base_url", ""))
                    return [u for u in urls if u]
            # durl 格式
            durl = pdata.get("durl")
            if durl:
                return [d.get("url", "") for d in durl if d.get("url")]
            return []

    async def fetch_user_videos(self, mid: str, max_count: int = 30) -> list[dict]:
        """获取用户视频列表。"""
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            await self._ensure_wbi(c)
            h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
            if self.cookie:
                h["Cookie"] = f"SESSDATA={self.cookie}"
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
                data = r.json().get("data", {})
                vlist = data.get("list", {}).get("vlist", [])
                if not vlist:
                    break
                videos.extend(vlist)
                total = data.get("page", {}).get("count", 0)
                if len(videos) >= total or len(videos) >= max_count:
                    break
                pn += 1
            return videos[:max_count]

    async def fetch_series_list(self, mid: str) -> list[dict]:
        """获取用户的合集/系列列表。"""
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            await self._ensure_wbi(c)
            h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
            if self.cookie:
                h["Cookie"] = f"SESSDATA={self.cookie}"
            # 获取用户合集
            params = {"mid": mid, "ps": "20", "pn": "1"}
            if self._img_key and self._sub_key:
                params = _wbi_sign(params, self._img_key, self._sub_key)
            url = f"{BASE_URL}/x/polymer/web-space/seasons_series_list"
            r = await c.get(url, params=params, headers=h, proxy=self.proxy)
            if r.status_code != 200:
                return []
            items = r.json().get("data", {}).get("items_lists", {})
            seasons = items.get("seasons_list", [])
            series = items.get("series_list", [])
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

    async def fetch_series_archives(self, mid: str, sid: int) -> list[dict]:
        """获取合集/系列视频列表。"""
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            await self._ensure_wbi(c)
            h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
            if self.cookie:
                h["Cookie"] = f"SESSDATA={self.cookie}"
            params = {"mid": mid, "series_id": str(sid), "ps": "30", "pn": "1"}
            if self._img_key and self._sub_key:
                params = _wbi_sign(params, self._img_key, self._sub_key)
            r = await c.get(SERIES_URL, params=params, headers=h, proxy=self.proxy)
            if r.status_code != 200:
                return []
            return r.json().get("data", {}).get("archives", [])

    async def fetch_favorite_list(self, fid: str = "0") -> list[dict]:
        """获取收藏夹内容列表。"""
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            await self._ensure_wbi(c)
            h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
            if self.cookie:
                h["Cookie"] = f"SESSDATA={self.cookie}"
            # 先获取默认收藏夹
            if fid == "0":
                fav_params = {"up_mid": ""}
                if self._img_key and self._sub_key:
                    fav_params = _wbi_sign(fav_params, self._img_key, self._sub_key)
                r0 = await c.get(f"{BASE_URL}/x/v3/fav/folder/created/list-all",
                                 params=fav_params, headers=h, proxy=self.proxy)
                if r0.status_code == 200:
                    folders = r0.json().get("data", {}).get("list", [])
                    if folders:
                        fid = str(folders[0].get("id", "0"))
            # 获取收藏夹内容
            all_items = []
            pn = 1
            while True:
                params = {"media_id": fid, "pn": str(pn), "ps": "20", "order": "mtime"}
                if self._img_key and self._sub_key:
                    params = _wbi_sign(params, self._img_key, self._sub_key)
                r = await c.get(FAVORITE_URL, params=params, headers=h, proxy=self.proxy)
                if r.status_code != 200:
                    break
                data = r.json().get("data", {})
                medias = data.get("medias") or []
                if not medias:
                    break
                all_items.extend(medias)
                if not data.get("has_more", False):
                    break
                pn += 1
            return all_items

    async def fetch_comments(self, bvid: str, cid: int, max_count: int = 50) -> list[dict]:
        """采集视频评论。"""
        from curl_cffi.requests import AsyncSession
        # 获取 aid
        aid = 0
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
            if self.cookie:
                h["Cookie"] = f"SESSDATA={self.cookie}"
            params = {"bvid": bvid}
            if self._img_key and self._sub_key:
                params = _wbi_sign(params, self._img_key, self._sub_key)
            r = await c.get(VIEW_URL, params=params, headers=h, proxy=self.proxy)
            if r.status_code == 200:
                aid = r.json().get("data", {}).get("aid", 0)
        if not aid:
            return []
        comments = []
        next_offset = ""
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
            if self.cookie:
                h["Cookie"] = f"SESSDATA={self.cookie}"
            while len(comments) < max_count:
                url = f"{BASE_URL}/x/v2/reply/main"
                params = {"oid": str(aid), "type": "1", "mode": "3"}
                if next_offset:
                    params["next"] = next_offset
                r = await c.get(url, params=params, headers=h, proxy=self.proxy)
                if r.status_code != 200:
                    break
                data = r.json().get("data", {})
                cursor = data.get("cursor", {})
                replies = data.get("replies") or []
                if not replies:
                    break
                comments.extend(replies)
                next_offset = str(cursor.get("next", ""))
                if not cursor.get("is_end", False):
                    continue
                break
        return comments[:max_count]

    async def fetch_user_info(self, mid: str) -> dict:
        """获取用户资料。"""
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            h = {"User-Agent": USERAGENT, "Referer": "https://www.bilibili.com/"}
            if self.cookie:
                h["Cookie"] = f"SESSDATA={self.cookie}"
            params = {"mid": mid}
            if self._img_key and self._sub_key:
                params = _wbi_sign(params, self._img_key, self._sub_key)
            r = await c.get(f"{BASE_URL}/x/web-interface/card", params=params, headers=h, proxy=self.proxy)
            if r.status_code != 200:
                return {}
            card = r.json().get("data", {}).get("card", {})
            if not card:
                return {}
            return {
                "name": card.get("name", ""),
                "fans": card.get("fans", 0),
                "following": card.get("attention", 0),
                "sign": card.get("sign", ""),
                "level": card.get("level", 0),
            }
