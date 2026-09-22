"""快手平台操作表。"""
from pathlib import Path
from shared.core.ops import PlatformOps, FeatureMeta, FeatureResult
from shared.core.storage import StorageOps, StorageConfig, safe_name
from shared.core.config import ConfigManager


class KuaishouOps(PlatformOps):
    platform_id = "kuaishou"
    display_name = "Kuaishou"
    cookie_hint = "需要 Cookie"

    features = [
        FeatureMeta("download", "下载单个作品", True),
        FeatureMeta("account",  "批量下载账号作品", True),
    ]

    async def _get_adapter(self, cookie: str):
        from .adapter import KuaishouAdapter
        from shared.core.adapter import PlatformConfig
        return KuaishouAdapter(config=PlatformConfig(
            name="kuaishou", display_name=self.display_name,
            domains=["kuaishou.com"], cookie=cookie))

    async def _do_download(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("kuaishou")
        try:
            from shared.flow.link import LinkExtractor
            from shared.flow.download import FileDownloader
            from shared.core.session import create_async_client
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, "kuaishou")
            finally:
                await client.close()
            if not links:
                return FeatureResult(False, "未提取到有效链接")
            log, files = [], []
            def _log(msg):
                log.append(msg)
                self.log(msg)
            for i, link in enumerate(links, 1):
                _log(f"[{i}/{len(links)}] {link.url[:60]}")
                raw = await adapter.request_detail(link)
                if not raw:
                    _log("  获取详情失败"); continue
                work = adapter.parse_detail(raw)
                if not work:
                    _log("  解析失败"); continue
                _log(f"  {work.get('author_name', '?')}: {work.get('title', '')[:40]}")
                urls = adapter.get_download_urls(work)
                if not urls:
                    _log("  无下载地址"); continue
                target = storage.resolve(work)
                dlc = create_async_client()
                try:
                    dl = FileDownloader(client=dlc, save_dir=target.parent)
                    result = await dl.download_file(urls[0], target.name)
                finally:
                    await dlc.close()
                if result:
                    _log(f"  ✓ {result}")
                    files.append(str(result))
                else:
                    _log("  ✗ 下载失败")
            return FeatureResult(True, f"处理 {len(links)} 个链接", log=log, files=files)
        finally:
            await adapter.close()

    async def _do_account(self, url, cookie, save_dir, selected=None) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("kuaishou")
        try:
            user_id = url.strip().rstrip("/").split("/")[-1]
            if not user_id:
                return FeatureResult(False, "无法提取用户ID")
            log = [f"用户: {user_id}"]
            cache_key = f"ks_account:{user_id}"
            videos = self._cache_get(cache_key)
            if videos is None:
                videos = await adapter.fetch_user_videos(user_id)
                if not videos:
                    return FeatureResult(False, "获取用户作品失败或为空", log=log)
                self._cache_put(cache_key, videos)
            log.append(f"共 {len(videos)} 个视频")

            # ── 第一阶段：返回预览（封面/标题/时长/点赞）──
            if selected is None:
                items = [self._video_preview(v, user_id) for v in videos]
                return FeatureResult(True, f"共 {len(items)} 个作品，待选择下载",
                                     data=items, preview="batch", log=log)

            # ── 第二阶段：下载勾选项 ──
            sel = {str(s) for s in selected}
            targets = [v for v in videos
                       if str(v.get("photoId") or v.get("id") or "") in sel]
            if not targets:
                return FeatureResult(False, "未匹配到勾选的作品（列表可能已过期，请重新执行）",
                                     log=log)
            from shared.flow.download import FileDownloader
            from shared.core.session import create_async_client
            files = []
            for i, v in enumerate(targets, 1):
                title = v.get("caption", "")[:40] or v.get("title", "")[:40] or "unknown"
                photo_id = v.get("photoId", "") or v.get("id", "")
                log.append(f"[{i}/{len(targets)}] {title}")
                video_url = v.get("mainMvUrl", "") or v.get("url", "")
                if not video_url:
                    log.append("  无下载地址"); continue
                work = {"platform": "kuaishou", "work_id": photo_id, "title": title,
                        "author_name": user_id}
                target = storage.resolve(work)
                dlc = create_async_client()
                try:
                    dl = FileDownloader(client=dlc, save_dir=target.parent)
                    result = await dl.download_file(video_url, target.name)
                finally:
                    await dlc.close()
                if result:
                    log.append(f"  ✓ {result}")
                    files.append(str(result))
                else:
                    log.append("  ✗ 下载失败")
            return FeatureResult(True, f"批量下载 {len(files)}/{len(targets)} 个",
                                 log=log, files=files)
        finally:
            await adapter.close()

    @staticmethod
    def _video_preview(v: dict, author: str = "") -> dict:
        """列表项 → 预览条目。字段按快手 profile/feed 结构防御式提取。"""
        cover = ""
        for key in ("coverUrls", "coverUrl", "poster", "thumbnailUrl"):
            c = v.get(key)
            if isinstance(c, list) and c and isinstance(c[0], dict):
                cover = c[0].get("url") or cover
                if cover:
                    break
            elif isinstance(c, str) and c:
                cover = c
                break
        duration = v.get("duration") or v.get("videoDuration") or 0
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            duration = 0
        if duration > 36000:  # 毫秒兜底（>10小时视为毫秒）
            duration //= 1000
        return {
            "platform": "kuaishou",
            "work_id": str(v.get("photoId") or v.get("id") or ""),
            "title": v.get("caption") or v.get("title") or "",
            "author_name": author,
            "cover": cover,
            "duration": duration,
            "digg_count": v.get("likeCount") or v.get("diggCount") or 0,
            "extra": "",
        }

    # ---- 批量列表缓存：预览→选择→下载 两阶段避免重复翻页 ----
    _CACHE_TTL = 1800  # 秒

    def _cache_get(self, key: str):
        import time
        ent = getattr(self, "_list_cache", {}).get(key)
        if ent and time.time() - ent[0] < self._CACHE_TTL:
            return ent[1]
        return None

    def _cache_put(self, key: str, items: list):
        import time
        if not hasattr(self, "_list_cache"):
            self._list_cache = {}
        self._list_cache[key] = (time.time(), items)
