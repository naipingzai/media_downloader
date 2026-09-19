"""服务器模式下的空进度条实现。"""

__all__ = ["FakeProgress"]


class FakeProgress:
    """在服务器模式下替代 Rich Progress，避免终端输出。"""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def add_task(self, *args, **kwargs) -> int:
        return 0

    def update(self, *args, **kwargs):
        pass

    def remove_task(self, *args, **kwargs):
        pass

    def advance(self, *args, **kwargs):
        pass

    def stop(self):
        pass
