"""字符串截断与美化工具。"""

__all__ = ["beautify_string", "trim_string"]


def beautify_string(text: str, max_length: int = 25, suffix: str = "...") -> str:
    """截断长字符串并在末尾添加省略号。"""
    if not text or len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def trim_string(text: str, max_length: int = 128) -> str:
    """简单截断字符串。"""
    return text[:max_length] if text else ""
