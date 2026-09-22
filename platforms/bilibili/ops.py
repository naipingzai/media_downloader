"""Bilibili platform ops — 完整实现。"""
from pathlib import Path
from shared.core.ops import PlatformOps, FeatureMeta, FeatureResult
from shared.core.config import ConfigManager


class BilibiliOps(PlatformOps):
    platform_id = "bilibili"
    display_name = "Bilibili"
    cookie_hint = "需要 SESSDATA Cookie（从浏览器 DevTools 复制）"

    features = [
        FeatureMeta("download",   "下载单个视频",       True),
        FeatureMeta("account",    "批量下载用户作品",   True),
        FeatureMeta("series",     "批量下载合集/系列",  True),
        FeatureMeta("collection", "批量下载收藏夹",     True),
        FeatureMeta("comment",    "采集视频评论",       True),
        FeatureMeta("user",       "采集用户资料",       True),
    ]

    async def _get_adapter(self, cookie: str):
        from .adapter import BilibiliAdapter
        from shared.core.adapter import PlatformConfig
        return BilibiliAdapter(config=PlatformConfig(
            name="bilibili", display_name=self.display_name,
            domains=["bilibili.com"], cookie=cookie))

    async def _do_download(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("bilibili")
        try:
            from shared.flow.link import LinkExtractor
            from shared.flow.download import FileDownloader
            from shared.core.session import create_async_client
            client = create_async_client()
            try:
                links = await LinkExtractor(client).run(url, "bilibili")
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
                _log(f"  {work['author_name']}: {work['title'][:40]}")
                urls = adapter.get_download_urls(work)
                if not urls:
                    bvid = work.get('work_id', '')
                    urls = await adapter.fetch_playurl(bvid)
                if not urls:
                    _log("  无下载地址"); continue
                for _n in self._quality_note(adapter): _log(_n)
                target = storage.resolve(work)
                dlc = create_async_client()
                try:
                    dl = FileDownloader(client=dlc, save_dir=target.parent)
                    result = await self._dash_download(dl, urls, target, _log)
                    if result:
                        files.append(result)
                finally:
                    await dlc.close()
            return FeatureResult(True, f"处理 {len(links)} 个视频", log=log, files=files)
        finally:
            await adapter.close()

    async def _do_account(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("bilibili")
        try:
            mid = self._extract_mid(url)
            if not mid:
                return FeatureResult(False, "无法从链接提取用户ID，需要 bilibili.com/space/MID 格式")
            log = [f"用户 MID: {mid}"]
            videos = await adapter.fetch_user_videos(mid)
            if not videos:
                return FeatureResult(False, "获取用户作品失败或作品为空", log=log)
            log.append(f"共 {len(videos)} 个视频")
            from shared.flow.download import FileDownloader
            from shared.core.session import create_async_client
            files = []
            for i, v in enumerate(videos, 1):
                bvid = v.get("bvid", "")
                title = v.get("title", "unknown")[:40]
                log.append(f"[{i}/{len(videos)}] {title}")
                urls = await adapter.fetch_playurl(bvid)
                if not urls:
                    log.append("  无下载地址"); continue
                for _n in self._quality_note(adapter): log.append(_n)
                work = {"platform": "bilibili", "work_id": bvid, "title": title,
                        "author_name": v.get("owner", {}).get("name", "")}
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
            return FeatureResult(True, f"用户 {mid} 共下载 {len(files)} 个视频", log=log, files=files)
        finally:
            await adapter.close()

    async def _do_series(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("bilibili")
        try:
            mid = self._extract_mid(url)
            sid = self._extract_id(url, "sid") or self._extract_id(url, "series_id")
            if not mid:
                return FeatureResult(False, "无法提取用户ID")
            if not sid:
                # 列出所有合集
                series_list = await adapter.fetch_series_list(mid)
                if not series_list:
                    return FeatureResult(False, "未找到合集/系列", log=[f"MID: {mid}"])
                log = [f"用户 {mid} 的合集/系列:"]
                for s in series_list:
                    log.append(f"  [{s.get('meta', {}).get('series_id', '')}] {s.get('meta', {}).get('name', '')} ({s.get('meta', {}).get('total', 0)}个)")
                return FeatureResult(True, f"共 {len(series_list)} 个合集", log=log)
            # 下载指定合集
            videos = await adapter.fetch_series_archives(mid, int(sid))
            if not videos:
                return FeatureResult(False, "合集为空或获取失败", log=[f"MID: {mid}, SID: {sid}"])
            log = [f"合集 {sid}: {len(videos)} 个视频"]
            files = await self._batch_download(adapter, videos, storage, log)
            return FeatureResult(True, f"合集下载 {len(files)}/{len(videos)}", log=log, files=files)
        finally:
            await adapter.close()

    async def _do_collection(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        storage = ConfigManager.get_storage_ops("bilibili")
        try:
            # 从URL提取收藏夹ID (fid)
            fid = self._extract_id(url, "fid") or "0"  # 0=默认收藏夹
            media_list = await adapter.fetch_favorite_list(fid)
            if not media_list:
                return FeatureResult(False, "收藏夹为空或获取失败", log=[f"收藏夹ID: {fid}"])
            log = [f"收藏夹 {fid}: {len(media_list)} 个作品"]
            from shared.flow.download import FileDownloader
            from shared.core.session import create_async_client
            files = []
            for i, item in enumerate(media_list, 1):
                upper = item.get("upper", {})
                title = item.get("title", "unknown")[:40]
                bvid = item.get("bv_id", "")
                log.append(f"[{i}/{len(media_list)}] {upper.get('name', '?')}: {title}")
                if not bvid:
                    log.append("  无BV号，跳过"); continue
                urls = await adapter.fetch_playurl(bvid)
                if not urls:
                    log.append("  无下载地址"); continue
                for _n in self._quality_note(adapter): log.append(_n)
                work = {"platform": "bilibili", "work_id": bvid, "title": title,
                        "author_name": upper.get("name", "")}
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
            return FeatureResult(True, f"收藏夹下载 {len(files)}/{len(media_list)}", log=log, files=files)
        finally:
            await adapter.close()

    async def _do_comment(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        try:
            raw = await adapter.request_detail(url)
            if not raw:
                return FeatureResult(False, "获取视频信息失败")
            work = adapter.parse_detail(raw)
            if not work:
                return FeatureResult(False, "解析视频信息失败")
            bvid = work.get("work_id", "")
            cid = 0
            try:
                cid = raw.get("view", {}).get("cid", 0) if isinstance(raw, dict) else 0
            except Exception:
                pass
            # cid 为0时尝试从 pagelist 获取
            if not cid and bvid:
                cid = await adapter.fetch_cid(bvid)
            log = [f"视频: {work['title'][:40]}", f"BV: {bvid}, cid: {cid}"]
            if not cid:
                return FeatureResult(False, "无法获取视频cid", log=log)
            comments = await adapter.fetch_comments(bvid, cid)
            if not comments:
                return FeatureResult(True, "无评论或获取失败（可能需要Cookie）", log=log)
            log.append(f"共 {len(comments)} 条评论")
            data = []
            for c in comments:
                member = c.get("member", {}) if isinstance(c, dict) else {}
                content = c.get("content", {}) if isinstance(c, dict) else {}
                data.append({
                    "user": member.get("uname", ""),
                    "text": content.get("message", ""),
                    "digg_count": c.get("like", 0),
                })
            return FeatureResult(True, f"采集 {len(comments)} 条评论", log=log, data=data)
        finally:
            await adapter.close()

    async def _do_user(self, url, cookie, save_dir) -> FeatureResult:
        adapter = await self._get_adapter(cookie)
        try:
            mid = self._extract_mid(url)
            if not mid:
                return FeatureResult(False, "无法从链接提取用户ID")
            user_data = await adapter.fetch_user_info(mid)
            if not user_data:
                return FeatureResult(False, "获取用户资料失败")
            log = [f"用户 MID: {mid}"]
            name = user_data.get("name", "")
            log.append(f"昵称: {name}")
            data = [{"field": "昵称", "value": name},
                    {"field": "MID", "value": str(mid)},
                    {"field": "粉丝", "value": user_data.get("fans", 0)},
                    {"field": "关注", "value": user_data.get("following", 0)},
                    {"field": "签名", "value": user_data.get("sign", "")},
                    {"field": "等级", "value": user_data.get("level", 0)}]
            return FeatureResult(True, f"用户: {name}", log=log, data=data)
        finally:
            await adapter.close()

    # ── DASH 下载合并 ──
    async def _dash_download(self, dl, urls: list, target, log) -> str | None:
        """下载DASH流并合并。返回合并后文件路径。log 可以是 list 或 callable。"""
        from shared.core import USERAGENT
        dl.client.headers.update({
            "User-Agent": USERAGENT,
            "Referer": "https://www.bilibili.com/",
        })
        def _l(msg):
            if callable(log):
                log(msg)
            else:
                log.append(msg)
        if len(urls) >= 2:
            _l("  下载视频流...")
            v = await dl.download_file(urls[0], f"{target.stem}_v.mp4")
            _l("  下载音频流...")
            a = await dl.download_file(urls[1], f"{target.stem}_a.mp4")
            if not v or not a:
                _l("  ✗ 下载失败"); return None
            _l("  合并音视频...")
            from shared.core.ffmpeg import FFmpegManager
            exe = FFmpegManager.find_executable()
            if exe:
                import subprocess
                merged = str(target.with_suffix(".mp4"))
                cmd = [str(exe), "-y", "-i", str(v), "-i", str(a),
                       "-c:v", "copy", "-c:a", "aac", merged]
                proc = subprocess.run(cmd, capture_output=True, timeout=120)
                v.unlink(missing_ok=True)
                a.unlink(missing_ok=True)
                if proc.returncode == 0:
                    _l(f"  ✓ 合并完成: {target.name}")
                    return merged
                _l("  ✗ 合并失败")
            else:
                _l("  ✗ FFmpeg未安装，保留分离文件")
            return None
        else:
            result = await dl.download_file(urls[0], target.name)
            return str(result) if result else None

    # ── 工具方法 ──

    @staticmethod
    def _quality_note(adapter) -> list[str]:
        """根据 fetch_playurl 实际拿到的清晰度生成提示日志。"""
        notes = []
        q = getattr(adapter, "last_quality", "")
        if q:
            notes.append(f"  清晰度: {q}")
        if getattr(adapter, "last_low", False):
            if getattr(adapter, "cookie", ""):
                notes.append("  ⚠ 清晰度偏低，SESSDATA 可能已失效，请重新登录")
            else:
                notes.append("  ⚠ 未登录，B站限制最高480P；配置 SESSDATA Cookie 后可下载1080P/4K 原画")
        return notes

    def _extract_mid(self, url: str) -> str:
        from re import compile
        m = compile(r"bilibili\.com/space/(\d+)").search(url)
        if m: return m.group(1)
        m = compile(r"uid=(\d+)").search(url)
        if m: return m.group(1)
        # 纯数字
        s = url.strip()
        if s.isdigit(): return s
        return ""

    def _extract_id(self, url: str, param: str) -> str:
        from re import compile
        m = compile(rf"{param}=(\d+)").search(url)
        return m.group(1) if m else ""

    async def _batch_download(self, adapter, videos: list, storage, log: list) -> list:
        from shared.flow.download import FileDownloader
        from shared.core.session import create_async_client
        files = []
        for i, v in enumerate(videos, 1):
            bvid = v.get("bvid", "") or v.get("work_id", "")
            title = v.get("title", "unknown")[:40]
            log.append(f"[{i}/{len(videos)}] {title}")
            if not bvid:
                log.append("  无BV号，跳过"); continue
            urls = await adapter.fetch_playurl(bvid)
            if not urls:
                log.append("  无下载地址"); continue
            for _n in self._quality_note(adapter): log.append(_n)
            work = {"platform": "bilibili", "work_id": bvid, "title": title,
                    "author_name": v.get("owner", {}).get("name", "") or v.get("author", {}).get("name", "")}
            target = storage.resolve(work)
            dlc = create_async_client()
            try:
                dl = FileDownloader(client=dlc, save_dir=target.parent)
                result = await self._dash_download(dl, urls, target, log)
                if result:
                    files.append(result)
            finally:
                await dlc.close()
        return files
