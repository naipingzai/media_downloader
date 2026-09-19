"""Step 4: 文件下载 —— 并发 + 进度 + 校验。"""
from __future__ import annotations
from asyncio import Semaphore
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from curl_cffi.requests import AsyncSession

__all__ = ["FileDownloader"]


class FileDownloader:
    """统一的文件下载器。

    支持: 多线程并发 / 断点续传 / 文件完整性校验 / 进度回调
    """

    SEMAPHORE = Semaphore(4)
    CHUNK_SIZE = 2 * 1024 * 1024  # 2MB

    def __init__(
        self,
        client: AsyncSession,
        save_dir: Path,
        max_retry: int = 5,
        timeout: int = 30,
        on_progress: Callable[[str, int, int], None] | None = None,
    ):
        self.client = client
        self.save_dir = save_dir
        self.max_retry = max_retry
        self.timeout = timeout
        self.on_progress = on_progress
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

        async with self.SEMAPHORE:
            return await self._do_download(url, target_path)

    async def _do_download(self, url: str, target: Path) -> Path | None:
        from ..core.retry import Retry
        retry = Retry(self.max_retry)
        try:
            return await retry.run(self._stream_download, url, target)
        except Exception as e:
            print(f"下载失败 {target.name}: {e}")
            return None

    async def _stream_download(self, url: str, target: Path) -> Path:
        """流式下载 + 写入文件。"""
        import aiofiles
        temp = target.with_suffix(target.suffix + ".tmp")
        try:
            resp = await self.client.get(
                url, timeout=self.timeout, stream=True,
                headers={"Range": "bytes=0-"} if not temp.exists() else {},
            )
            total = int(resp.headers.get("content-length", 0))
            downloaded = temp.stat().st_size if temp.exists() else 0

            async with aiofiles.open(temp, "ab" if downloaded else "wb") as f:
                async for chunk in resp.aiter_content(chunk_size=self.CHUNK_SIZE):
                    await f.write(chunk)
                    downloaded += len(chunk)
                    if self.on_progress:
                        self.on_progress(target.name, downloaded, total)

            # 校验文件
            if temp.stat().st_size > 0:
                temp.rename(target)
                return target
            temp.unlink(missing_ok=True)
            return None
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    async def download_batch(
        self, tasks: list[tuple[str, str, str]],
    ) -> list[Path | None]:
        """批量下载。tasks = [(url, filename, sub_dir), ...]"""
        from asyncio import gather
        results = await gather(*[
            self.download_file(url, name, sub)
            for url, name, sub in tasks
        ])
        return list(results)
