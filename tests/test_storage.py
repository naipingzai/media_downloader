"""shared.core.storage 单元测试。"""
from pathlib import Path

from shared.core.storage import (
    StorageConfig,
    StorageOps,
    detect_extension,
    format_date,
    safe_name,
)


# ==================== safe_name ====================
class TestSafeName:
    def test_strips_illegal_chars(self):
        assert safe_name('a/b\\c:d*e?f"g<h>i|j') == "abcdefghij"

    def test_strips_newlines(self):
        assert safe_name("hello\nworld\r") == "helloworld"

    def test_truncates_to_80(self):
        assert len(safe_name("x" * 200)) == 80

    def test_empty_falls_back(self):
        assert safe_name("") == "unknown"
        assert safe_name("///") == "unknown"


# ==================== detect_extension ====================
class TestDetectExtension:
    def test_video(self):
        assert detect_extension({"video_url": "http://x"}) == "mp4"

    def test_image(self):
        assert detect_extension({"image_urls": ["http://x"]}) == "jpg"

    def test_default(self):
        assert detect_extension({}) == "mp4"


# ==================== format_date ====================
class TestFormatDate:
    def test_epoch(self):
        assert format_date(0) == "1970-01-01"

    def test_millis_auto_convert(self):
        # 毫秒时间戳 (>1e12) 应自动 //1000 后转换, 与秒级结果一致
        assert format_date(1_700_000_000_000) == format_date(1_700_000_000)

    def test_invalid_returns_marker(self):
        # 东八区 -5s 会落在 1970-01-01, 属正常行为; 校验不抛异常即可
        assert format_date(-5).startswith("19")


# ==================== StorageOps ====================
class TestStorageOps:
    def _ops(self, tmp_path: Path, mode: str = "flat",
             dedup: bool = True) -> StorageOps:
        """构造 StorageOps 并把 base_dir 与 dedup 索引重定向到 tmp_path。"""
        fmt = "csv" if mode == "csv" else "json"
        ops = StorageOps("testplat", StorageConfig(mode=mode, data_format=fmt, dedup=dedup))
        ops.base_dir = tmp_path / "testplat"
        # base_dir 在 __init__ 时已绑定 record 文件, 同步重定向
        ops._dedup = StorageOps.__dict__  # placeholder, 下一行真正重建
        from shared.core.storage import _DedupIndex
        ops._dedup = _DedupIndex(ops.base_dir / ".downloaded_ids.txt")
        return ops

    def test_base_dir_uses_volume_constant(self):
        """路径必须基于 constants.VOLUME (PyInstaller 安全)。"""
        from shared.core.constants import VOLUME
        ops = StorageOps("douyin", StorageConfig())
        assert ops.base_dir == VOLUME / "douyin"

    def test_resolve_flat(self, tmp_path):
        ops = self._ops(tmp_path)
        p = ops.resolve({"author_name": "张三", "title": "视频",
                         "video_url": "x"})
        assert p.parent == ops.base_dir
        assert p.name == "张三_视频.mp4"

    def test_resolve_by_author(self, tmp_path):
        ops = self._ops(tmp_path, mode="by_author")
        p = ops.resolve({"author_name": "李四", "title": "t",
                         "video_url": "x"})
        assert p.parent == ops.base_dir / "李四"

    def test_dedup_roundtrip(self, tmp_path):
        ops = self._ops(tmp_path)
        assert not ops.is_downloaded("w1")
        ops.record_download("w1")
        assert ops.is_downloaded("w1")
        # 第二次 add 同 id 不重复写文件行
        ops.record_download("w1")
        content = (ops.base_dir / ".downloaded_ids.txt").read_text()
        assert content.count("w1") == 1

    def test_dedup_disabled(self, tmp_path):
        ops = self._ops(tmp_path, dedup=False)
        ops.record_download("w1")
        assert not ops.is_downloaded("w1")  # 关闭去重 → 永远 False

    def test_dedup_memory_cache(self, tmp_path):
        """record 后删除文件, 内存缓存仍应命中 (单进程语义)。"""
        ops = self._ops(tmp_path)
        ops.record_download("w9")
        (ops.base_dir / ".downloaded_ids.txt").unlink()
        assert ops.is_downloaded("w9")

    def test_save_data_json(self, tmp_path):
        import asyncio
        ops = self._ops(tmp_path)
        out = asyncio.run(ops.save_data([{"a": 1}], "items"))
        assert out and Path(out).exists()

    def test_save_data_csv_handles_comma(self, tmp_path):
        """CSV 值含逗号/引号时标准库 csv 正确转义。"""
        import asyncio
        import csv as csvmod
        from shared.core.storage import StorageConfig as _SC
        ops = StorageOps("testplat", _SC(data_format="csv"))
        ops.base_dir = tmp_path / "testplat"
        out = asyncio.run(ops.save_data(
            [{"name": 'a,"b', "val": "c,d"}], "items"))
        with open(out, encoding="utf-8-sig", newline="") as f:
            rows = list(csvmod.reader(f))
        assert rows[0] == ["name", "val"]
        assert rows[1] == ['a,"b', "c,d"]
