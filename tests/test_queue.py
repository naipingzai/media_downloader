"""shared.flow.queue 下载队列单元测试。"""
from shared.flow.queue import DownloadHandle, DownloadQueue, get_queue


class TestDownloadQueue:
    def test_singleton(self):
        assert get_queue() is get_queue()

    def test_register_unregister(self):
        q = get_queue()
        h = DownloadHandle(name="t")
        q.register("k1", h)
        assert any(s["key"] == "k1" for s in q.status())
        q.unregister("k1")
        assert not any(s["key"] == "k1" for s in q.status())

    def test_stop_task_prefix_match(self):
        q = get_queue()
        h = DownloadHandle()
        q.register("douyin:download:abc", h)
        n = q.stop_task("douyin:download")
        assert n >= 1
        assert h.stopped
        q.unregister("douyin:download:abc")

    def test_pause_resume(self):
        q = get_queue()
        q.pause_all()
        assert q.paused
        q.resume_all()
        assert not q.paused

    def test_speed_limit(self):
        q = get_queue()
        q.set_speed_limit(500)
        assert q.speed_limit == 500
        q.set_speed_limit(0)
        assert q.speed_limit == 0

    def test_stop_all(self):
        q = get_queue()
        h1, h2 = DownloadHandle(), DownloadHandle()
        q.register("a", h1)
        q.register("b", h2)
        q.stop_all()
        assert h1.stopped and h2.stopped
