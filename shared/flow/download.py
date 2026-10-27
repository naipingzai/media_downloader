"""Step 4: 文件下载 —— 并发 + 进度 + 校验 + 断点续传。"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from curl_cffi.requests import AsyncSession

__all__ = ["FileDownloader"]


class FileDownloader:
    """统一的文件下载器。

    支持: 并发控制 / 断点续传 (Range) / 完整性校验 / 进度回调
    """

    CHUNK_SIZE = 2 * 1024 * 1024  # 2MB

    def __init__(
        self,
        client: AsyncSession,
        save_dir: Path,
        max_retry: int = 5,
        timeout: int = 30,
        max_workers: int = 4,
        on_progress: Callable[[str, int, int], None] | None = None,
    ):
        self.client = client
        self.save_dir = save_dir
        self.max_retry = max_retry
        self.timeout = timeout
        self.on_progress = on_progress
        # 信号量实例化 (原为类属性: 全实例共享, 且与 max_workers 配置脱节)
        self._semaphore = asyncio.Semaphore(max(1, max_workers))
        self.save_dir.mkdir(parents=True, exist_ok=True)

    async def download_file(
        self,
        url: str,
        filename: str,
        sub_dir: str = "",
    ) -> Path | None:
        """下载单个文件，返回保存路径。"""
        target_dir = self.save_dir / sub_dir if sub_dir else self.save_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        # 已存在则跳过
        if target_path.exists() and target_path.stat().st_size > 0:
            return target_path
        async with self._semaphore:
            return await self._do_download(url, target_path)

    async def _do_download(self, url: str, target: Path) -> Path | None:
        from ..core.logger import get_logger
        from ..core.retry import Retry

        log = get_logger("flow.download")
        retry = Retry(self.max_retry)
        try:
            return await retry.run(self._stream_download, url, target)
        except Exception as e:
            log.error("下载失败 %s: %s", target.name, e)
            return None

    async def _stream_download(self, url: str, target: Path) -> Path:
        """流式下载 + 断点续传。

        断点续传关键: temp 已有 partial 时必须携带
        `Range: bytes={已有大小}-` 请求头, 服务器返回 206 部分内容;
        若服务器不支持 Range (返回 200 全量), 则重头写 ("wb") 避免拼接损坏。
        """
        import aiofiles

        temp = target.with_suffix(target.suffix + ".tmp")
        downloaded = temp.stat().st_size if temp.exists() else 0
        headers = {"Range": f"bytes={downloaded}-"} if downloaded else {}

        resp = await self.client.get(
            url, timeout=self.timeout, stream=True, headers=headers,
        )
        # 服务器不支持 Range → 全量重下 (覆盖而非追加)
        resumed = (
            downloaded > 0
            and getattr(resp, "status_code", 0) == 206
        )
        total = int(resp.headers.get("content-length", 0))
        if resumed:
            total += downloaded
        elif downloaded:
            # 200 全量响应: 丢弃旧 partial
            downloaded = 0

        mode = "ab" if resumed else "wb"
        async with aiofiles.open(temp, mode) as f:
            async for chunk in resp.aiter_content(chunk_size=self.CHUNK_SIZE):
                await f.write(chunk)
                downloaded += len(chunk)
                if self.on_progress:
                    self.on_progress(target.name, downloaded, total)

        # 校验文件非空后落盘
        if temp.stat().st_size > 0:
            temp.rename(target)
            return target
        temp.unlink(missing_ok=True)
        return None

    async def download_batch(
        self, tasks: list[tuple[str, str, str]],
    ) -> list[Path | None]:
        """批量下载。tasks = [(url, filename, sub_dir), ...]"""
        results = await asyncio.gather(*[
            self.download_file(url, name, sub)
            for url, name, sub in tasks
        ])
        return list(results)
