"""Xiaohongshu/RedNote platform adapter - HTML parsing."""
from shared.core import (
    PlatformAdapter, PlatformConfig, IMPERSONATE,
)
from .. import register_platform

@register_platform("xiaohongshu")
class XiaohongshuAdapter(PlatformAdapter):
    DOMAINS = ["xiaohongshu.com", "rednote.com"]
    DISPLAY_NAME = "Xiaohongshu / RedNote"

    def __init__(self, config: PlatformConfig | None = None, **kwargs):
        self.config = config or PlatformConfig(name="xiaohongshu", display_name=self.DISPLAY_NAME, domains=self.DOMAINS, **kwargs)
        self.cookie = self.config.cookie
        self.proxy = self.config.proxy

    def get_config_schema(self) -> dict:
        return {"cookie": {"type": "str", "label": "Cookie"}, "proxy": {"type": "str", "label": "Proxy"}}

    async def extract_links(self, url: str) -> list[str]:
        from re import compile
        patterns = [compile(r"https?://(?:www\.)?xiaohongshu\.com/\S+"), compile(r"https?://(?:www\.)?rednote\.com/\S+"), compile(r"https?://xhslink\.com/\S+")]
        return [u for p in patterns for u in p.findall(url)]

    async def request_detail(self, link) -> dict | None:
        from curl_cffi.requests import AsyncSession
        url = link.url if hasattr(link, "url") else str(link)
        h = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.xiaohongshu.com/",
        }
        if self.cookie: h["Cookie"] = self.cookie
        async with AsyncSession(impersonate=IMPERSONATE) as c:
            r = await c.get(url, headers=h, timeout=15, proxy=self.proxy)
            if r.status_code == 200: return {"html": r.text, "url": url}
            return None

    def parse_detail(self, raw: dict) -> dict | None:
        html = raw.get("html", "")
        if not html: return None
        marker = "window.__INITIAL_STATE__="
        start = html.find(marker)
        if start == -1: return None
        start += len(marker)
        end = html.find("</script>", start)
        if end == -1: return None
        raw_json = html[start:end].rstrip(";").strip()
        from json import loads
        try:
            data = loads(raw_json.replace("undefined", "null"))
        except Exception:
            return None
        note = data.get("note", {}).get("noteDetailMap", {})
        if not note: return None
        note_data = next(iter(note.values()), {}).get("note", {})
        if not note_data: return None
        user = note_data.get("user", {})
        title = note_data.get("title", "") or note_data.get("desc", "")[:50]
        images = [img.get("urlDefault", "") for img in note_data.get("imageList", []) if img.get("urlDefault")]
        video_url = ""
        video = note_data.get("video", {})
        if video:
            media = video.get("media", {})
            video_url = media.get("stream", {}).get("h264", [{}])[0].get("masterUrl", "") if media.get("stream") else media.get("consumer", {}).get("originVideoKey", "")
        note_type = note_data.get("type", "")
        return {
            "platform": "xiaohongshu", "work_id": note_data.get("noteId", ""),
            "type": note_type,
            "title": title, "author_name": user.get("nickname", ""),
            "author_id": user.get("userId", ""),
            "video_url": video_url, "image_urls": images,
            "is_video": note_type == "video" or bool(video_url),
            "is_live": note_type == "normal" and not video_url and len(images) > 0,
            "digg_count": note_data.get("interactInfo", {}).get("likedCount", 0),
            "comment_count": note_data.get("interactInfo", {}).get("commentCount", 0),
        }

    def get_download_urls(self, work: dict) -> list[str]:
        urls = []
        if work.get("video_url"): urls.append(work["video_url"])
        urls.extend(work.get("image_urls", []))
        return urls

    async def get_account_works(self, user_id: str, pages: int = 0) -> list[dict]: return []
    async def close(self): pass

    # ===== 统一扩展接口 =====
    async def fetch_user_profile(self, sec_uid: str):
        """拉取用户资料。优先 H5 接口, 失败回落到占位。"""
        from shared.core.adapter import norm_user
        try:
            from curl_cffi.requests import AsyncSession
            h = {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
                              " AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"),
                "Referer": "https://www.xiaohongshu.com/",
            }
            if self.cookie: h["Cookie"] = self.cookie
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                r = await c.get(
                    f"https://www.xiaohongshu.com/user/profile/{sec_uid}",
                    headers=h, timeout=15, proxy=self.proxy)
                if r.status_code == 200:
                    # 从页面 JSON 提取 user
                    marker = "window.__INITIAL_STATE__="
                    idx = r.text.find(marker)
                    if idx > -1:
                        start = idx + len(marker)
                        end = r.text.find("</script>", start)
                        if end > -1:
                            from json import loads
                            try:
                                data = loads(r.text[start:end].rstrip(";").strip()
                                              .replace("undefined", "null"))
                                user = (data.get("user") or {}).get("user", {})
                                if not user:
                                    user = data.get("user", {})
                                if not user:
                                    user_page = data.get("user", {}).get("userPage", {})
                                    user = user_page.get("user", {}) or user_page
                                if user:
                                    return norm_user(user, "xiaohongshu")
                            except Exception:
                                pass
        except Exception:
            pass
        return norm_user({"userId": sec_uid, "nickname": sec_uid, "platform": "xiaohongshu"}, "xiaohongshu")

    async def fetch_user_posts(self, sec_uid: str, count: int = 20, max_cursor: str = "0"):
        """拉取小红书用户作品 (H5 /api/sns/web/v1/user_posted)。"""
        from shared.core.adapter import norm_work
        try:
            from curl_cffi.requests import AsyncSession
            h = {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
                              " AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"),
                "Referer": f"https://www.xiaohongshu.com/user/profile/{sec_uid}",
            }
            if self.cookie: h["Cookie"] = self.cookie
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                r = await c.get(
                    "https://edith.xiaohongshu.com/api/sns/web/v1/user_posted",
                    params={"user_id": sec_uid, "cursor": max_cursor or "", "num": count},
                    headers=h, timeout=15, proxy=self.proxy)
                if r.status_code != 200:
                    return []
                try:
                    payload = r.json()
                except Exception:
                    return []
                if not payload.get("success"):
                    return []
                notes = (payload.get("data") or {}).get("notes") or []
                out = []
                for n in notes:
                    note_card = n.get("note_card") or n
                    out.append(norm_work({
                        "noteId": note_card.get("note_id") or n.get("note_id", ""),
                        "title": note_card.get("title") or note_card.get("display_title", ""),
                        "type": note_card.get("type", "normal"),
                        "user": {
                            "nickname": note_card.get("user", {}).get("nickname", ""),
                            "userId": note_card.get("user", {}).get("user_id", ""),
                        },
                        "interactInfo": {
                            "likedCount": note_card.get("interact_info", {}).get("liked_count", 0),
                            "commentCount": note_card.get("interact_info", {}).get("comment_count", 0),
                        },
                        "cover": (note_card.get("cover") or {}).get("url_default", ""),
                        "video": note_card.get("video"),
                        "imageList": note_card.get("image_list") or [],
                    }, "xiaohongshu"))
                return out
        except Exception:
            return []

    async def fetch_current_user(self):
        """获取当前登录小红书用户 (从 /api/sns/web/v1/user/self_info)。"""
        from shared.core.adapter import norm_user
        try:
            from curl_cffi.requests import AsyncSession
            h = {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
                              " AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"),
                "Referer": "https://www.xiaohongshu.com/",
            }
            if self.cookie: h["Cookie"] = self.cookie
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                r = await c.get(
                    "https://edith.xiaohongshu.com/api/sns/web/v1/user/self_info",
                    headers=h, timeout=15, proxy=self.proxy)
                if r.status_code != 200:
                    return None
                try:
                    payload = r.json()
                except Exception:
                    return None
                if not payload.get("success"):
                    return None
                user = (payload.get("data") or {}).get("user") or {}
                if not user:
                    return None
                return norm_user({
                    "userId": user.get("user_id", ""),
                    "nickname": user.get("nickname", ""),
                    "avatar": user.get("avatar", ""),
                    "signature": user.get("desc", ""),
                    "follower_count": user.get("fans", 0),
                    "following_count": user.get("follows", 0),
                    "aweme_count": user.get("notes", 0),
                }, "xiaohongshu")
        except Exception:
            return None

    async def fetch_collection(self, cursor: str = "0", count: int = 20):
        """拉取小红书收藏作品 (从 /api/sns/web/v1/collection/list)。"""
        from shared.core.adapter import norm_work
        try:
            from curl_cffi.requests import AsyncSession
            h = {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
                              " AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"),
                "Referer": "https://www.xiaohongshu.com/",
            }
            if self.cookie: h["Cookie"] = self.cookie
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                items = []
                pcursor = cursor or ""
                while len(items) < count:
                    r = await c.get(
                        "https://edith.xiaohongshu.com/api/sns/web/v1/collection/list",
                        params={"cursor": pcursor, "num": count},
                        headers=h, timeout=15, proxy=self.proxy)
                    if r.status_code != 200:
                        break
                    try:
                        payload = r.json()
                    except Exception:
                        break
                    if not payload.get("success"):
                        break
                    notes = (payload.get("data") or {}).get("notes") or []
                    if not notes:
                        break
                    for n in notes:
                        note_card = n.get("note_card") or n
                        items.append(norm_work({
                            "noteId": note_card.get("note_id") or n.get("note_id", ""),
                            "title": note_card.get("title") or note_card.get("display_title", ""),
                            "type": note_card.get("type", "normal"),
                            "user": {
                                "nickname": note_card.get("user", {}).get("nickname", ""),
                                "userId": note_card.get("user", {}).get("user_id", ""),
                            },
                            "interactInfo": {
                                "likedCount": note_card.get("interact_info", {}).get("liked_count", 0),
                            },
                            "cover": (note_card.get("cover") or {}).get("url_default", ""),
                            "video": note_card.get("video"),
                            "imageList": note_card.get("image_list") or [],
                        }, "xiaohongshu"))
                    pcursor = str((payload.get("data") or {}).get("cursor", ""))
                    if not pcursor or pcursor == "0":
                        break
                return items[:count]
        except Exception:
            return None

    async def fetch_user_following(self, sec_uid: str, count: int = 20, max_time: str = "0"):
        """拉取小红书关注列表 (从 /api/sns/web/v1/user/followings)。"""
        from shared.core.adapter import norm_user
        try:
            from curl_cffi.requests import AsyncSession
            h = {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
                              " AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"),
                "Referer": f"https://www.xiaohongshu.com/user/profile/{sec_uid}",
            }
            if self.cookie: h["Cookie"] = self.cookie
            async with AsyncSession(impersonate=IMPERSONATE) as c:
                users = []
                cursor = max_time or ""
                while len(users) < count:
                    r = await c.get(
                        "https://edith.xiaohongshu.com/api/sns/web/v1/user/followings",
                        params={"user_id": sec_uid, "cursor": cursor, "num": count},
                        headers=h, timeout=15, proxy=self.proxy)
                    if r.status_code != 200:
                        break
                    try:
                        payload = r.json()
                    except Exception:
                        break
                    if not payload.get("success"):
                        break
                    arr = (payload.get("data") or {}).get("users") or []
                    if not arr:
                        break
                    for u in arr:
                        users.append(norm_user(u, "xiaohongshu"))
                    cursor = str((payload.get("data") or {}).get("cursor", ""))
                    if not cursor or cursor == "0":
                        break
                return {"followings": users[:count], "has_more": False} if users else None
        except Exception:
            return None
