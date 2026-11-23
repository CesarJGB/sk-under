import base64

from Crypto.Cipher import DES
from Crypto.Util.Padding import pad


def encode_payload(plaintext: str, key: bytes, iv: bytes) -> bytes:
    cipher = DES.new(key, DES.MODE_CBC, iv)
    return base64.b64encode(cipher.encrypt(pad(plaintext.encode("utf-8"), DES.block_size)))
