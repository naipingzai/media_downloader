"""机密数据加密 —— Cookie 等敏感信息的 Fernet 对称加密。

设计:
- 密钥文件 Volume/.secret_key (0600 权限), 首次访问自动生成。
- 落盘格式: cookies.json 中值形如 "enc:<base64>" 的为密文,
  兼容读取旧版明文 (无前缀), 写入时一律加密 —— 平滑升级, 无需迁移脚本。
"""
from __future__ import annotations

import base64
import os

__all__ = ["encrypt_value", "decrypt_value", "is_encrypted"]

_PREFIX = "enc:"
_KEY_FILE = None  # 惰性初始化 (避免 import 时触发 VOLUME 副作用检查)
_KEY_CACHE: bytes | None = None


def _key_file():
    from .constants import VOLUME
    global _KEY_FILE
    if _KEY_FILE is None:
        _KEY_FILE = VOLUME / ".secret_key"
    return _KEY_FILE


def _load_key() -> bytes:
    """读取 (或生成) Fernet 密钥。"""
    global _KEY_CACHE
    if _KEY_CACHE is not None:
        return _KEY_CACHE
    from cryptography.fernet import Fernet

    kf = _key_file()
    if kf.is_file():
        try:
            key = kf.read_bytes().strip()
            Fernet(key)  # 校验有效性
            _KEY_CACHE = key
            return key
        except Exception:
            pass  # 密钥损坏 → 重新生成 (旧密文将无法解密, 回退为重新登录)
    key = Fernet.generate_key()
    kf.parent.mkdir(parents=True, exist_ok=True)
    # 仅限当前用户读写
    try:
        os.chmod(kf.parent, 0o700)
    except OSError:
        pass
    kf.write_bytes(key)
    try:
        os.chmod(kf, 0o600)
    except OSError:
        pass
    _KEY_CACHE = key
    return key


def encrypt_value(plain: str) -> str:
    """明文 → "enc:<base64 密文>"。空串原样返回。"""
    if not plain:
        return plain
    from cryptography.fernet import Fernet
    token = Fernet(_load_key()).encrypt(plain.encode("utf-8"))
    return _PREFIX + token.decode("ascii")


def decrypt_value(stored: str) -> str:
    """"enc:<base64>" → 明文; 非密文 (旧版明文) 原样返回。"""
    if not stored or not is_encrypted(stored):
        return stored
    from cryptography.fernet import Fernet, InvalidToken
    token = stored[len(_PREFIX):].encode("ascii")
    try:
        return Fernet(_load_key()).decrypt(token).decode("utf-8")
    except (InvalidToken, Exception):
        # 密钥不匹配/损坏 → 视为无效, 清空处理 (引导用户重新登录)
        return ""


def is_encrypted(stored: str) -> bool:
    return bool(stored) and stored.startswith(_PREFIX)
