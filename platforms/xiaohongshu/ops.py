"""小红书平台操作表。"""
from pathlib import Path
from shared.core.ops import PlatformOps, FeatureMeta, FeatureResult
from shared.core.config import ConfigManager


class XiaohongshuOps(PlatformOps):
    platform_id = "xiaohongshu"
    display_name = "Xiaohongshu / RedNote"
    cookie_hint = ""

    features = [
        FeatureMeta("download", "下载单个作品", True),
    ]

    async def _get_adapter(self, cookie: str):
        from .adapter import XiaohongshuAdapter
        from shared.core.adapter import PlatformConfig
        return XiaohongshuAdapter(config=PlatformConfig(
            name="xiaohongshu", display_name=self.display_name,
            domains=["xiaohongshu.com", "rednote.com"], cookie=cookie))

    async def _do_download(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("xiaohongshu")
        try:
            from shared.flow.link import LinkExtractor
            from shared.flow.download import FileDownloader
            from shared.core.session import create_async_client
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, "xiaohongshu")
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
                    is_video = work.get("is_video", False)
                    for j, file_url in enumerate(urls):
                        if is_video and j == 0:
                            ext = "mp4"
                        else:
                            ext = "jpg"
                        fname = f"{target.stem}_{j+1}.{ext}" if len(urls) > 1 else f"{target.stem}.{ext}"
                        result = await dl.download_file(file_url, fname)
                        if result:
                            log.append(f"  ✓ {result}")
                            files.append(str(result))
                        else:
                            log.append(f"  ✗ 文件 {j+1} 下载失败")
                finally:
                    await dlc.close()
            return FeatureResult(True, f"处理 {len(links)} 个链接", log=log, files=files)
        finally:
            await adapter.close()
