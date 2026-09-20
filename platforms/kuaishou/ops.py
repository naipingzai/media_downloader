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
            for i, link in enumerate(links, 1):
                log.append(f"[{i}/{len(links)}] {link.url[:60]}")
                raw = await adapter.request_detail(link)
                if not raw:
                    log.append("  获取详情失败"); continue
                work = adapter.parse_detail(raw)
                if not work:
                    log.append("  解析失败"); continue
                log.append(f"  {work.get('author_name', '?')}: {work.get('title', '')[:40]}")
                urls = adapter.get_download_urls(work)
                if not urls:
                    log.append("  无下载地址"); continue
                target = storage.resolve(work)
                dlc = create_async_client()
                try:
                    dl = FileDownloader(client=dlc, save_dir=target.parent)
                    result = await dl.download_file(urls[0], target.name)
                finally:
                    await dlc.close()
                if result:
                    log.append(f"  ✓ {result}")
                    files.append(str(result))
                else:
                    log.append("  ✗ 下载失败")
            return FeatureResult(True, f"处理 {len(links)} 个链接", log=log, files=files)
        finally:
            await adapter.close()

    async def _do_account(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("kuaishou")
        try:
            user_id = url.strip().rstrip("/").split("/")[-1]
            if not user_id:
                return FeatureResult(False, "无法提取用户ID")
            log = [f"用户: {user_id}"]
            videos = await adapter.fetch_user_videos(user_id)
            if not videos:
                return FeatureResult(False, "获取用户作品失败或为空", log=log)
            log.append(f"共 {len(videos)} 个视频")
            from shared.flow.download import FileDownloader
            from shared.core.session import create_async_client
            files = []
            for i, v in enumerate(videos, 1):
                title = v.get("caption", "")[:40] or v.get("title", "")[:40] or "unknown"
                photo_id = v.get("photoId", "") or v.get("id", "")
                log.append(f"[{i}/{len(videos)}] {title}")
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
            return FeatureResult(True, f"用户 {user_id} 共下载 {len(files)} 个视频", log=log, files=files)
        finally:
            await adapter.close()
