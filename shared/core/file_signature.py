"""文件类型签名检测。"""
from pathlib import Path

from .constants import FILE_SIGNATURES, FILE_SIGNATURES_LENGTH

__all__ = ["FileSignature"]


class FileSignature:
    """通过文件头字节判断文件类型。"""

    @staticmethod
    def detect(file_path: str | Path) -> str:
        """读取文件头部字节，返回文件扩展名；无法识别时返回空字符串。"""
        try:
            with open(file_path, "rb") as f:
                header = f.read(FILE_SIGNATURES_LENGTH)
        except (OSError, IOError):
            return ""
        for offset, signature, ext in FILE_SIGNATURES:
            if header[offset : offset + len(signature)] == signature:
                return ext
        return ""
