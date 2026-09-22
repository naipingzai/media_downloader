"""快手 QR 码登录。"""
import httpx
import qrcode
from io import BytesIO
from PIL import Image
from shared.core.login import PlatformLoginManager, LoginBus

API_BASE = "https://account.kuaishou.com"
QR_TOKEN = "/rest/cc/pc/login/token"
QR_POLL = "/rest/cc/pc/login/qrcode/poll"
QR_PAGE = "https://cp.kuaishou.com/article/profile"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


class KuaishouLoginManager(PlatformLoginManager):
    platform_id = "kuaishou"

    def __init__(self):
        self._client = httpx.Client(
            base_url=API_BASE,
            headers={"User-Agent": UA},
            timeout=30.0,
        )

    def generate_qr(self) -> tuple[str, str, Image.Image]:
        resp = self._client.get(QR_TOKEN)
        resp.raise_for_status()
        data = resp.json().get("result", 1)
        if data != 1:
            raise RuntimeError(f"快手QR生成失败: {resp.text}")
        token = resp.json().get("token", "")
        if not token:
            raise RuntimeError(f"快手QR生成失败: 无token")
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(QR_PAGE)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return QR_PAGE, token, img

    def check_qr_status(self, token: str) -> dict:
        resp = self._client.get(QR_POLL, params={"kuaishou": "kuaishou", "token": token})
        resp.raise_for_status()
        data = resp.json()
        result = {}
        if data.get("result") == 1:  # 已登录
            result["code"] = 0
            result["cookies"] = {}
            for ck in resp.cookies.jar:
                if ck.value:
                    result["cookies"][ck.name] = ck.value
            for ck in self._client.cookies.jar:
                if ck.value:
                    result["cookies"][ck.name] = ck.value
        elif data.get("result") == 50:  # 过期
            result["code"] = 86038
        else:  # 等待中
            result["code"] = 86090
        return result

    def close(self):
        self._client.close()
