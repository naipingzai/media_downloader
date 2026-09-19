"""Step 1: 链接提取 —— 短链解析 + 正则匹配 + ID分类。"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlparse, parse_qs

if TYPE_CHECKING:
    from curl_cffi.requests import AsyncSession

__all__ = ["LinkExtractor", "ExtractedLink", "LinkType"]


class LinkType(Enum):
    UNKNOWN = "unknown"
    DETAIL = "detail"       # 单作品
    ACCOUNT = "account"     # 账号主页
    MIX = "mix"             # 合集/播放列表
    LIVE = "live"           # 直播
    COLLECTION = "collection"  # 收藏
    SEARCH = "search"       # 搜索
    HOT = "hot"             # 热榜
    COMMENT = "comment"     # 评论


@dataclass
class ExtractedLink:
    """提取后的结构化链接信息。"""
    url: str
    link_type: LinkType
    platform: str           # "douyin" / "kuaishou" / "xiaohongshu"
    work_id: str = ""       # 作品ID
    user_id: str = ""       # 用户ID
    mix_id: str = ""        # 合集ID
    sec_user_id: str = ""   # sec_user_id
    extra: dict | None = None


class LinkExtractor:
    """从用户输入文本中提取有效链接。

    流程:
    1. 识别短链接 → HTTP 重定向获取长链接
    2. 正则匹配各平台URL模式
    3. 从URL中提取ID
    4. 分类链接类型
    """

    def __init__(self, client: AsyncSession):
        self.client = client

    async def run(self, text: str, platform: str = "") -> list[ExtractedLink]:
        """从文本中提取所有有效链接。"""
        urls = self._split_urls(text)
        results = []
        for url in urls:
            # 短链接先解析为长链接
            resolved = await self._resolve_short_url(url)
            link = self._classify_url(resolved, platform)
            if link:
                results.append(link)
        return results

    def _split_urls(self, text: str) -> list[str]:
        """将文本按空格/换行分割为URL列表。"""
        import re
        return [u for u in re.split(r"[\s\n]+", text.strip()) if u.startswith("http")]

    async def _resolve_short_url(self, url: str) -> str:
        """短链接通过HTTP重定向获取最终URL。"""
        short_domains = [
            "v.douyin.com", "v.kuaishou.com", "xhslink.com", "xhslink.cn",
            "vm.tiktok.com", "vt.tiktok.com",
        ]
        parsed = urlparse(url)
        if any(d in parsed.netloc for d in short_domains):
            try:
                resp = await self.client.get(url, allow_redirects=True, max_redirects=5)
                return str(resp.url)
            except Exception:
                return url
        return url

    def _classify_url(self, url: str, platform: str = "") -> ExtractedLink | None:
        """根据URL模式分类链接类型。"""
        import re

        # 抖音
        if "douyin.com" in url or "iesdouyin.com" in url:
            p = platform or "douyin"
            return self._classify_douyin(url, p)
        # TikTok
        if "tiktok.com" in url:
            return self._classify_tiktok(url)
        # 快手
        if "kuaishou.com" in url:
            return self._classify_kuaishou(url)
        # 小红书
        if "xiaohongshu.com" in url or "rednote.com" in url:
            return self._classify_xiaohongshu(url)
        return None

    def _classify_douyin(self, url: str, platform: str) -> ExtractedLink | None:
        from re import compile
        # 作品
        m = compile(r"/(?:video|note|slides)/(\d{19})").search(url)
        if m:
            return ExtractedLink(url=url, link_type=LinkType.DETAIL, platform=platform, work_id=m.group(1))
        # 账号
        m = compile(r"/user/([A-Za-z0-9_-]+)").search(url)
        if m:
            uid = m.group(1)
            sec = parse_qs(urlparse(url).query).get("sec_user_id", [""])[0]
            return ExtractedLink(url=url, link_type=LinkType.ACCOUNT, platform=platform, user_id=uid, sec_user_id=sec)
        # 合集
        m = compile(r"/collection/(\d{19})").search(url)
        if m:
            return ExtractedLink(url=url, link_type=LinkType.MIX, platform=platform, mix_id=m.group(1))
        # 直播
        m = compile(r"live\.douyin\.com/(\d+)").search(url)
        if m:
            return ExtractedLink(url=url, link_type=LinkType.LIVE, platform=platform, work_id=m.group(1))
        return None

    def _classify_tiktok(self, url: str) -> ExtractedLink | None:
        from re import compile
        m = compile(r"/@[^/]+/(?:video|photo)/(\d{19})").search(url)
        if m:
            return ExtractedLink(url=url, link_type=LinkType.DETAIL, platform="tiktok", work_id=m.group(1))
        m = compile(r"/@([^/]+)").search(url)
        if m:
            return ExtractedLink(url=url, link_type=LinkType.ACCOUNT, platform="tiktok", user_id=m.group(1))
        return None

    def _classify_kuaishou(self, url: str) -> ExtractedLink | None:
        from re import compile
        m = compile(r"short-video/([A-Za-z0-9_-]+)").search(url)
        if m:
            return ExtractedLink(url=url, link_type=LinkType.DETAIL, platform="kuaishou", work_id=m.group(1))
        m = compile(r"/profile/([A-Za-z0-9_-]+)").search(url)
        if m:
            return ExtractedLink(url=url, link_type=LinkType.ACCOUNT, platform="kuaishou", user_id=m.group(1))
        return None

    def _classify_xiaohongshu(self, url: str) -> ExtractedLink | None:
        from re import compile
        m = compile(r"/explore/(\w+)").search(url)
        if m:
            return ExtractedLink(url=url, link_type=LinkType.DETAIL, platform="xiaohongshu", work_id=m.group(1))
        m = compile(r"/user/profile/(\w+)").search(url)
        if m:
            return ExtractedLink(url=url, link_type=LinkType.ACCOUNT, platform="xiaohongshu", user_id=m.group(1))
        return None
