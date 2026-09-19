"""格式化工具函数。"""
from http.cookies import SimpleCookie
from re import compile

__all__ = [
    "cookie_str_to_dict",
    "cookie_dict_to_str",
    "format_size",
]

_COOKIE_PATTERN = compile(r"(?P<key>[^=;,]+)=(?P<value>[^;,]+)")


def cookie_str_to_dict(cookie_str: str) -> dict:
    """将 Cookie 字符串转为字典（使用正则，兼容复杂格式）。"""
    if not cookie_str:
        return {}
    cookie = {}
    for match in _COOKIE_PATTERN.finditer(cookie_str):
        key = match.group("key").strip()
        value = match.group("value").strip()
        cookie[key] = value
    return cookie


def cookie_dict_to_str(cookie_dict: dict) -> str:
    """将 Cookie 字典转为字符串。"""
    return "; ".join(f"{k}={v}" for k, v in cookie_dict.items())


def format_size(size: int | float) -> str:
    """将字节数格式化为可读字符串。"""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"
