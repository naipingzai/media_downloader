"""Douyin/TikTok platform adapter — all APIs."""
from shared.core import (
    PlatformAdapter, PlatformConfig,
    PARAMS_HEADERS, USERAGENT, IMPERSONATE,
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
        # Cookie 中的 msToken 比空串可信: 受保护接口会校验其有效性
        self.mstoken = next((v for k, v in d.items() if k.lower() == "mstoken"), "")
        self.last_error = ""

    def get_config_schema(self) -> dict:
        return {"cookie": {"type": "str", "label": "Cookie"}, "proxy": {"type": "str", "label": "Proxy"}}

    async def extract_links(self, url: str) -> list[str]:
        from re import compile
        return [u for p in [compile(r"https?://(?:www\.)?douyin\.com/\S+"), compile(r"https?://v\.douyin\.com/\S+"), compile(r"https?://(?:www\.)?tiktok\.com/\S+")] for u in p.findall(url)]

    # ---- common signed request ----

    async def _signed_get(self, api_url: str, extra_params: dict) -> dict | None:
        from curl_cffi.requests import AsyncSession
        from platforms.douyin.encrypt import DouYinParams
        h = PARAMS_HEADERS.copy()
        h["Cookie"] = self.cookie
        h["uifid"] = self.uifid
        err = ""
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            # 重试 2 次: 每次重算签名 (a_bogus 含时间戳, 复用旧签名必然失效)
            for attempt in (1, 2):
                q = self._base_params() | extra_params
                if self.mstoken and not q.get("msToken"):
                    q["msToken"] = self.mstoken
                signed = DouYinParams().sign_url(
                    api_url, q, method="GET", user_agent=USERAGENT)
                try:
                    r = await c.get(f"{api_url}?{signed}", headers=h,
                                    proxy=self.proxy)
                except Exception as e:
                    err = f"网络异常: {type(e).__name__}"
                    continue
                if r.status_code != 200:
                    err = f"HTTP {r.status_code}"
                    continue
                try:
                    data = r.json()
                except Exception:
                    err = "响应不是 JSON (可能被风控拦截)"
                    continue
                if isinstance(data, dict) and data.get("status_code") not in (None, 0):
                    err = (f"接口 status_code={data.get('status_code')}"
                           " (Cookie 可能过期, 请重新登录)")
                self.last_error = err
                return data
        self.last_error = err or "未知错误"
        return None

    # ---- detail ----

    async def request_detail(self, link) -> dict | None:
        work_id = str(getattr(link, "work_id", "") or "")
        if not work_id:
            # 短链兜底场景: 上游重定向失败时 work_id 为空, 这里再解析一次
            raw_url = str(getattr(link, "url", "") or "")
            work_id = await self._resolve_work_id_from_url(raw_url)
        if not work_id:
            self.last_error = "无法获取作品ID (短链解析失败, 请检查网络或重试)"
            return None
        data = await self._signed_get(
            "https://www.douyin.com/aweme/v1/web/aweme/detail/",
            {"uifid": self.uifid, "msToken": "", "aweme_id": work_id})
        if isinstance(data, dict) and data.get("aweme_detail"):
            return data
        # 签名/风控失效时回退分享页解析 (不依赖 a_bogus/WebSign)
        page = await self._fetch_detail_from_share_page(work_id)
        if page:
            self.last_error = ""
            return page
        return data

    async def _resolve_work_id_from_url(self, url: str) -> str:
        """从短链/长链中解析作品 ID (重试 3 次)。

        用于上游 LinkExtractor 重定向失败、work_id 为空时的二次兜底。
        """
        import re
        if not url:
            return ""
        m = re.search(r"/(?:video|note|slides)/(\d{15,25})", url)
        if m:
            return m.group(1)
        if "douyin.com" not in url:
            return ""
        from curl_cffi.requests import AsyncSession
        h = PARAMS_HEADERS.copy()
        h["User-Agent"] = USERAGENT
        if self.cookie:
            h["Cookie"] = self.cookie
        for _ in range(3):
            try:
                async with AsyncSession(impersonate=IMPERSONATE) as c:
                    r = await c.get(url, headers=h, proxy=self.proxy,
                                    allow_redirects=True, timeout=10)
                m = re.search(r"/(?:video|note|slides)/(\d{15,25})", str(r.url))
                if m:
                    return m.group(1)
                if r.text:
                    m = re.search(r'"aweme_id"\s*:\s*"(\d{15,25})"', r.text)
                    if m:
                        return m.group(1)
            except Exception:
                continue
        return ""

    async def _fetch_detail_from_share_page(self, work_id: str) -> dict | None:
        """回退方案: 解析作品分享页内嵌 JSON。

        签名接口被风控 (403/空返回) 时, 分享页仍内嵌作品数据
        (window._ROUTER_DATA / RENDER_DATA), 可直接取出 aweme_detail。
        """
        from curl_cffi.requests import AsyncSession
        h = PARAMS_HEADERS.copy()
        if self.cookie:
            h["Cookie"] = self.cookie
        # 图文作品用 /share/note/ 或 /share/slides/; 视频用 /share/video/
        for kind in ("video", "note", "slides"):
            url = f"https://www.iesdouyin.com/share/{kind}/{work_id}/"
            try:
                async with AsyncSession(impersonate=IMPERSONATE) as c:
                    # 单路径 8s: 三种路径最坏 24s, 避免用户长时间等待
                    r = await c.get(url, headers=h, proxy=self.proxy,
                                    allow_redirects=True, timeout=8)
                if r.status_code != 200 or not r.text:
                    continue
                aweme = self._extract_aweme_from_html(r.text, work_id)
                if aweme:
                    return {"aweme_detail": aweme}
            except Exception:
                continue
        return None

    @staticmethod
    def _extract_aweme_from_html(html: str, work_id: str) -> dict | None:
        """从分享页 HTML 中找出目标作品 dict (兼容多种内嵌格式)。"""
        import json
        import re
        from urllib.parse import unquote
        blobs: list[str] = []
        # window._ROUTER_DATA = {...}; 用花括号配平提取完整 JSON。
        # (正则非贪婪 \{.*?\} 会在第一个 '}' 处截断, 导致 json.loads 失败)
        idx = html.find("window._ROUTER_DATA")
        if idx >= 0:
            start = html.find("{", idx)
            if start >= 0:
                blob = DouyinAdapter._balanced_json(html[start:])
                if blob:
                    blobs.append(blob)
        m = re.search(r'<script[^>]+id="RENDER_DATA"[^>]*>([^<]+)</script>',
                      html, re.S)
        if m:
            try:
                blobs.append(unquote(m.group(1).strip()))
            except Exception:
                pass

        def _find(node, depth: int = 0):
            if depth > 14:
                return None
            if isinstance(node, dict):
                if str(node.get("aweme_id") or "") == str(work_id):
                    return node
                for v in node.values():
                    got = _find(v, depth + 1)
                    if got:
                        return got
            elif isinstance(node, list):
                for v in node:
                    got = _find(v, depth + 1)
                    if got:
                        return got
            return None

        for blob in blobs:
            try:
                data = json.loads(blob)
            except Exception:
                continue
            aweme = _find(data)
            if aweme:
                return aweme
        return None

    @staticmethod
    def _balanced_json(text: str) -> str:
        """从首字符 '{' 起做花括号配平, 返回完整 JSON 文本 (失败返回空串)。

        需正确处理字符串内的 '{' '}' 与转义字符。
        """
        if not text or text[0] != "{":
            return ""
        depth = 0
        in_str = False
        esc = False
        for i, ch in enumerate(text):
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[:i + 1]
        return ""

    def parse_detail(self, raw: dict) -> dict | None:
        aweme = raw.get("aweme_detail") if isinstance(raw, dict) else None
        if not aweme: return None
        video = aweme.get("video", {}) or {}
        play = video.get("play_addr", {}).get("url_list", [])
        bit_rate = video.get("bit_rate", [])
        if bit_rate:
            best = max(bit_rate, key=lambda x: x.get("bit_rate", 0))
            play = best.get("play_addr", {}).get("url_list", []) or play
        author = aweme.get("author", {})
        # 图集 (图片动态) 检测: image_post_info / images / aweme_type 68
        try:
            image_urls = self.extract_images(aweme)
        except Exception:
            image_urls = []
        is_images = bool(image_urls)
        # 封面（取第一个可用; 图集取首图）
        cover = ""
        for key in ("cover", "origin_cover", "dynamic_cover"):
            c = video.get(key)
            if isinstance(c, dict):
                urls = c.get("url_list") or []
                if urls:
                    cover = urls[0]
                    break
        if not cover and image_urls:
            cover = image_urls[0]
        stat = aweme.get("statistics", {})
        # 所在合集 ID (作品属于合集时存在)
        mix_info = aweme.get("mix_info") or {}
        mix_id = str(mix_info.get("mix_id") or "")
        aweme_id = aweme.get("aweme_id", "")
        # 图集的分享链接用 /note/, 视频用 /video/
        share_url = (f"https://www.douyin.com/note/{aweme_id}" if is_images
                     else f"https://www.douyin.com/video/{aweme_id}")
        return {
            "platform": "douyin", "work_id": aweme_id,
            "title": aweme.get("desc", ""),
            "mix_id": mix_id,
            "author_name": author.get("nickname", ""),
            "author_id": author.get("uid", ""),
            "sec_user_id": author.get("sec_uid", ""),
            "media_type": "images" if is_images else "video",
            "image_urls": image_urls,
            # 图集没有真正的视频: video_url 置空, 避免幻灯片视频被当作品下载
            "video_url": "" if is_images else (play[0] if play else ""),
            "cover_url": cover,
            "duration": (0 if is_images
                         else int(video.get("duration") or 0) // 1000),
            "share_url": share_url,
            "digg_count": stat.get("digg_count", 0),
            "comment_count": stat.get("comment_count", 0),
            "view_count": stat.get("play_count", 0),
        }

    @staticmethod
    def extract_images(aweme: dict) -> list[str]:
        """提取图集图片地址 (兼容 image_post_info.images / 顶层 images / aweme_type=68)。

        关键守卫: 普通视频作品 (aweme_type=0 等) 的 API 响应也可能带顶层
        `images` 字段 (live_photo 静帧 / 推荐流冗余数据), 若不校验类型会把
        真视频误判成图集 → 视频地址被跳过、只下到几张图。
        仅以下情形认定为图集:
          a) image_post_info.images 标准图文结构存在;
          b) aweme_type ∈ {68, 150} (抖音图文/图集类型码) 且顶层 images 非空。
        """
        urls: list[str] = []
        def _pick(node: dict) -> str:
            if not isinstance(node, dict):
                return ""
            for key in ("display_image", "owner_watermark_image",
                        "user_watermark_image", "thumbnail_image"):
                sub = node.get(key)
                if isinstance(sub, dict):
                    lst = sub.get("url_list") or []
                    if lst:
                        return lst[0]
            lst = node.get("url_list") or []
            return lst[0] if lst else ""
        # 1) image_post_info.images (抖音图文标准结构) — 结构本身即可信
        ipi = aweme.get("image_post_info")
        if not isinstance(ipi, dict):
            ipi = {}
        imgs = ipi.get("images")
        if not isinstance(imgs, list):
            imgs = []
        for it in imgs:
            u = _pick(it)
            if u:
                urls.append(u)
        # 2) 顶层 images: 必须同时满足图文类型码, 防止普通视频误判
        if not urls:
            a_type = aweme.get("aweme_type")
            if a_type in (68, 150):
                top = aweme.get("images")
                if not isinstance(top, list):
                    top = []
                for it in top:
                    if not isinstance(it, dict):
                        continue
                    u = (it.get("url") if isinstance(it.get("url"), str)
                         else "") or _pick(it)
                    if u:
                        urls.append(u)
        return urls

    @staticmethod
    def is_image_post(aweme: dict) -> bool:
        """判断是否为图集/图文动态。

        与 extract_images 同一守卫: 顶层 images 必须配合图文类型码,
        否则普通视频 (aweme_type=0) 会被误判为图集。
        """
        if not isinstance(aweme, dict):
            return False
        if aweme.get("image_post_info"):
            return True
        if aweme.get("aweme_type") in (68, 150) and aweme.get("images"):
            return True
        return False

    def get_download_urls(self, work: dict) -> list[str]:
        images = [u for u in (work.get("image_urls") or []) if u]
        if images:
            return images
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
    # ---- user following list (关注列表) ----

    async def fetch_user_following(self, sec_user_id: str, count: int = 20, max_time: str = "0") -> dict | None:
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/user/follow/list/", {"sec_user_id": sec_user_id, "count": str(count), "max_time": max_time, "min_time": "0"})

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

    async def fetch_favorite_folder_list(self, cursor: str = "0", count: int = 20) -> dict | None:
        """获取用户自建收藏夹列表（需登录 Cookie）。"""
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/aweme/favorite_folder/list/", {"cursor": cursor, "count": str(count), "uifid": self.uifid, "msToken": ""})

    async def fetch_favorite_folder_awemes(self, folder_id: str, cursor: str = "0", count: int = 20) -> dict | None:
        """获取指定收藏夹内的作品列表（需登录 Cookie）。"""
        return await self._signed_get("https://www.douyin.com/aweme/v1/web/aweme/favorite_folder/aweme_list/", {"folder_id": folder_id, "cursor": cursor, "count": str(count), "uifid": self.uifid, "msToken": ""})

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

    # ===== 统一扩展接口 =====

    async def fetch_current_user(self):
        """获取当前登录用户 (Cookie 作者信息)。"""
        from shared.core.adapter import norm_user
        for url in ("https://www.douyin.com/aweme/v1/web/user/profile/self/",
                    "https://www.douyin.com/passport/web/account/info/"):
            resp = await self._signed_get(url, {})
            if not isinstance(resp, dict) or resp.get("status_code", -1) != 0:
                continue
            u = resp.get("user") or resp.get("user_info") or {}
            if not u:
                inner = resp.get("data") or {}
                if isinstance(inner, dict):
                    u = inner.get("user") or inner.get("user_info") or inner
            if u:
                return norm_user(u, "douyin")
        return None
