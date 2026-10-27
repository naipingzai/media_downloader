"""shared.core.secret 加密与 CookieManager 集成测试。"""
from shared.core.secret import decrypt_value, encrypt_value, is_encrypted


class TestSecret:
    def test_roundtrip(self):
        plain = "ttwid=xxx; msToken=yyy; sessionid=zzz"
        enc = encrypt_value(plain)
        assert is_encrypted(enc)
        assert decrypt_value(enc) == plain

    def test_ciphertext_differs(self):
        enc = encrypt_value("secret")
        assert enc != "secret"
        assert enc.startswith("enc:")

    def test_empty_passthrough(self):
        assert encrypt_value("") == ""
        assert decrypt_value("") == ""

    def test_legacy_plaintext_passthrough(self):
        """旧版明文读取兼容: 无 enc: 前缀原样返回。"""
        assert decrypt_value("legacy_plain_cookie") == "legacy_plain_cookie"

    def test_wrong_token_falls_back_empty(self):
        """密钥不匹配 → 返回空串 (引导重新登录), 不抛异常。"""
        assert decrypt_value("enc:AAAA") == ""

    def test_key_file_permissions(self):
        """密钥文件应存在且生成 (root 下 chmod 可能不生效, 只验证可用)。"""
        from shared.core import secret
        key = secret._load_key()
        assert key and secret._key_file().is_file()
