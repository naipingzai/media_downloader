"""Xiaohongshu/RedNote platform adapter - HTML parsing."""
from shared.core import (
    PlatformAdapter, PlatformConfig, DownloadResult,
    create_async_client, PARAMS_HEADERS, IMPERSONATE,
)
from shared.translation import _
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
