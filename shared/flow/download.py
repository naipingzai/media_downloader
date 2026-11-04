"""Step 4: 文件下载 —— 并发 + 进度 + 校验 + 断点续传 + 队列控制。"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from curl_cffi.requests import AsyncSession

__all__ = ["FileDownloader"]


def _referer_for(url: str) -> dict:
    """按资源域名返回防盗链头 (缺 Referer/UA 是 CDN 403 的常见原因)。"""
    u = (url or "").lower()
    if "douyin" in u or "douyinpic" in u or "douyinstatic" in u or "zjcdn" in u:
        return {"Referer": "https://www.douyin.com/"}
    if "bilibili" in u or "hdslb" in u or "akamaized" in u:
        return {"Referer": "https://www.bilibili.com/"}
    if "kuaishou" in u or "ksurl" in u or "gifshow" in u:
        return {"Referer": "https://www.kuaishou.com/"}
    if "xiaohongshu" in u or "xhscdn" in u:
        return {"Referer": "https://www.xiaohongshu.com/"}
    return {}


class FileDownloader:
    """统一的文件下载器。

    支持: 并发控制 / 断点续传 (Range) / 完整性校验 / 进度回调
          / 队列控制 (暂停·恢复·按任务停止·全局限速, 经 shared.flow.queue)
    """

    CHUNK_SIZE = 2 * 1024 * 1024  # 2MB

    def __init__(
        self,
        client: AsyncSession,
        save_dir: Path,
        max_retry: int = 5,
        timeout: int = 30,
        max_workers: int = 4,
        task_key: str = "",
        on_progress: Callable[[str, int, int], None] | None = None,
    ):
        self.client = client
        self.save_dir = save_dir
        self.max_retry = max_retry
        self.timeout = timeout
        self.on_progress = on_progress
        # task_key: 功能执行标识, 供 DownloadQueue 按任务停止 (UI 停止按钮)
        self.task_key = task_key
        self._handle = None
        self._queue = None
        self._reg_key = None
        # 按文件名累计进度 (批量下载时进度单调递增, 不会每个文件从 0 重爬)
        self._file_total: dict[str, int] = {}
        self._file_done: dict[str, int] = {}
        try:
            from .queue import DownloadHandle, get_queue
            self._queue = get_queue()
            self._handle = DownloadHandle(name=save_dir.name)
            self._reg_key = task_key or id(self)
            self._queue.register(self._reg_key, self._handle)
            # 任务已被停止 (UI 停止按钮) → 新建下载器立即继承, 避免批量中"停不掉"
            if task_key and self._queue.is_task_stopped(task_key):
                self._handle.stop_flag.set()
        except Exception:
            self._handle = None
        # 信号量实例化 (全实例独立, 支持按配置 max_workers 控制)
        self._semaphore = asyncio.Semaphore(max(1, max_workers))
        self.save_dir.mkdir(parents=True, exist_ok=True)

    @property
    def stopped(self) -> bool:
        """当前下载是否被队列停止 (UI 停止按钮 / stop_all)。"""
        return bool(self._handle and self._handle.stopped)

    def close(self) -> None:
        """释放队列句柄。

        必须在下载结束时调用 (或依赖 __del__ 兜底)。若不注销, 陈旧句柄会
        一直留在 DownloadQueue 中, 导致进度统计把历史任务算进去 →
        进度条恒显 100% 并来回跳动。
        """
        if self._queue is not None and self._reg_key is not None:
            try:
                self._queue.unregister(self._reg_key)
            except Exception:
                pass
            self._reg_key = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.close()
        return False

    def _sync_handle(self) -> None:
        """把各文件进度汇总到句柄, 供 UI 显示整体进度。

        按文件名做 key (重试时覆盖而非累加), 因此批量下载时
        进度条单调递增, 不会出现"每个文件从 0 重爬到 100%"的跳动。
        """
        if not self._handle:
            return
        self._handle.total = sum(self._file_total.values())
        self._handle.downloaded = sum(self._file_done.values())

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    async def download_file(
        self,
        url: str,
        filename: str,
        sub_dir: str = "",
    ) -> Path | None:
        """下载单个文件，返回保存路径。"""
        # 已停止则不再启动新文件 (批量场景下尽快退出)
        if self.stopped:
            return None
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

        headers.update(_referer_for(url))
        resp = await self.client.get(
            url, timeout=self.timeout, stream=True, headers=headers,
        )
        # 校验状态码: 4xx/5xx 不能当作成功落盘 (否则错误页被当图片/视频保存)
        status = getattr(resp, "status_code", 0)
        if status >= 400:
            from ..core.error import RetryableError
            raise RetryableError(f"HTTP {status} ({target.name})")
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
        self._file_total[target.name] = total
        self._sync_handle()

        mode = "ab" if resumed else "wb"
        async with aiofiles.open(temp, mode) as f:
            async for chunk in resp.aiter_content(chunk_size=self.CHUNK_SIZE):
                # 队列控制: 停止 → 中断; 暂停 → 异步挂起; 限速 → chunk 间节流
                if self.stopped:
                    raise InterruptedError(f"下载已停止: {target.name}")
                if self._queue and self._queue.paused:
                    while self._queue.paused and not self.stopped:
                        await asyncio.sleep(0.2)
                    if self.stopped:
                        raise InterruptedError(f"下载已停止: {target.name}")
                if self._queue and self._queue.speed_limit > 0:
                    delay = self.CHUNK_SIZE / (self._queue.speed_limit * 1024)
                    if delay > 0.01:
                        await asyncio.sleep(min(delay, 10.0))
                await f.write(chunk)
                downloaded += len(chunk)
                self._file_done[target.name] = downloaded
                self._sync_handle()
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
        """批量下载。tasks = [(url, filename, sub_dir), ...]

        顺序执行并逐项检查停止标志: 用户点击停止后立刻中断,
        不再继续排队剩余文件 (并发下载单文件内部仍有信号量控制)。
        """
        results: list[Path | None] = []
        for url, name, sub in tasks:
            if self.stopped:
                results.append(None)
                continue
            results.append(await self.download_file(url, name, sub))
        return results
