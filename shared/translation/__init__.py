"""旧版 gettext 兼容层 —— 仅保留接口, 不再支持语言切换。

仅中文, 平台旧代码 `from shared.translation import _; _("文本")` 仍可使用 (取到原文)。
"""
__all__ = ["_"]


def _(message: str) -> str:
    """中文模式下直接返回原文。"""
    return message
