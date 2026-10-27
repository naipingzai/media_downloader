"""shared.core.ops / retry / format 单元测试。"""
import asyncio

from shared.core.error import AuthError, FatalError, RateLimitedError
from shared.core.format import cookie_str_to_dict, format_size
from shared.core.ops import FeatureMeta, FeatureResult, PlatformBus, PlatformOps
from shared.core.retry import Retry


def run(coro):
    """不依赖 pytest-asyncio 的同步 async 执行器。"""
    return asyncio.run(coro)


# ==================== PlatformBus ====================
class _DummyOps(PlatformOps):
    platform_id = "dummy"
    display_name = "Dummy"
    cookie_hint = ""
    features = [
        FeatureMeta("download", "下载", True,
                    emits_work_info=True, group="work"),
        FeatureMeta("search", "搜索", True, group="platform"),
    ]

    async def _do_download(self, url, cookie, save_dir):
        return FeatureResult(True, "ok", data=[{"x": 1}])


class TestPlatformBus:
    def test_register_and_query(self):
        PlatformBus.register(_DummyOps())
        assert "dummy" in PlatformBus.list_platforms()
        ops = PlatformBus.get_ops("dummy")
        assert ops.display_name == "Dummy"
        assert PlatformBus.display_name_of("dummy") == "Dummy"

    def test_get_feature_by_id(self):
        PlatformBus.register(_DummyOps())
        f = PlatformBus.get_feature("dummy", "download")
        assert f is not None
        assert f.emits_work_info is True
        assert f.group == "work"
        assert PlatformBus.get_feature("dummy", "nope") is None

    def test_run_unknown_platform(self):
        r = run(PlatformBus.run("ghost", "download", "", "", None))
        assert not r.success
        assert "未注册" in r.message

    def test_run_dispatch(self):
        PlatformBus.register(_DummyOps())
        r = run(PlatformBus.run("dummy", "download", "", "", None))
        assert r.success and r.data == [{"x": 1}]

    def test_unimplemented_feature(self):
        PlatformBus.register(_DummyOps())
        r = run(PlatformBus.run("dummy", "ghost_fn", "", "", None))
        assert not r.success
        assert "未实现" in r.message


# ==================== Retry 分级 ====================
class TestRetry:
    def test_fatal_no_retry(self):
        """FatalError 立即抛出, 不重试。"""
        calls = 0

        async def boom():
            nonlocal calls
            calls += 1
            raise FatalError("bad param")

        try:
            run(Retry(max_retry=3).run(boom))
            raised = False
        except FatalError:
            raised = True
        assert raised
        assert calls == 1

    def test_auth_no_retry(self):
        calls = 0

        async def boom():
            nonlocal calls
            calls += 1
            raise AuthError("cookie expired")

        try:
            run(Retry(max_retry=3).run(boom))
            raised = False
        except AuthError:
            raised = True
        assert raised
        assert calls == 1

    def test_retryable_eventually_succeeds(self):
        calls = 0

        async def flaky():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RateLimitedError("429")
            return "ok"

        r = run(Retry(max_retry=5, base_delay=0.01).run(flaky))
        assert r == "ok"
        assert calls == 3

    def test_exhausted_raises_last(self):
        async def always_fail():
            raise RateLimitedError("still limited")

        try:
            run(Retry(max_retry=2, base_delay=0.01).run(always_fail))
            raised = False
        except RateLimitedError:
            raised = True
        assert raised


# ==================== FeatureMeta 兼容旧三参构造 ====================
class TestFeatureMetaCompat:
    def test_three_args_still_work(self):
        f = FeatureMeta("x", "功能X", True)
        assert f.need_url is True
        assert f.emits_work_info is False   # 默认值
        assert f.group == "platform"        # 默认值


# ==================== format ====================
class TestFormat:
    def test_cookie_str_to_dict(self):
        assert cookie_str_to_dict("a=1; b=2; c=3") == {
            "a": "1", "b": "2", "c": "3"}

    def test_format_size(self):
        assert "KB" in format_size(2048)
        assert "MB" in format_size(5 * 1024 * 1024)
