"""文件名清理工具。"""
from re import compile, sub

__all__ = ["Cleaner"]


class Cleaner:
    """清理文件名中的非法字符。"""

    ILLEGAL = compile(r"[^\u4e00-\u9ffa-zA-Z0-9\-_！？，。；：\u201c\u201d（）《》\s]")
    MULTI_UNDERSCORE = compile(r"_+")

    def __init__(self, extra_replacements: dict[str, str] | None = None):
        self.replacements = extra_replacements or {" ": " "}

    def filter_name(self, name: str, default: str = "") -> str:
        """清理文件名，返回安全的名称。"""
        if not name or not name.strip():
            return default
        for old, new in self.replacements.items():
            name = name.replace(old, new)
        name = self.ILLEGAL.sub("_", name)
        name = self.MULTI_UNDERSCORE.sub("_", name)
        return name.strip("_").strip()

    def clean_path(self, path: str) -> str:
        """清理路径中的危险字符。"""
        return self.filter_name(path, "Download")
