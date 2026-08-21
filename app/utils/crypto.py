"""API Key 加密工具（四层架构第二层：业务层密钥安全）。

使用 AES-256-GCM 加密，密钥由 SECRET_KEY 经 SHA-256 派生。
- 密文带随机 nonce，每次加密结果不同
- GCM 认证标签防篡改
- 解密失败返回 None（不抛异常，避免信息泄露）
"""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.settings.config import settings

# 前缀标记，便于识别密文
PREFIX = "enc:v1:"


def _derive_key() -> bytes:
    """从 SECRET_KEY 派生 32 字节 AES 密钥"""
    return hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()


def encrypt_secret(plaintext: str) -> str:
    """加密明文，返回 base64 密文（带前缀）"""
    if not plaintext:
        return ""
    key = _derive_key()
    nonce = os.urandom(12)  # 96-bit nonce
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return PREFIX + base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_secret(encoded: str) -> str:
    """解密密文；失败返回空串"""
    if not encoded or not encoded.startswith(PREFIX):
        return ""
    try:
        raw = base64.b64decode(encoded[len(PREFIX):])
        nonce, ciphertext = raw[:12], raw[12:]
        key = _derive_key()
        return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")
    except Exception:
        return ""


def mask_key(api_key: str) -> str:
    """脱敏显示：只保留前 6 位和后 4 位"""
    if not api_key:
        return ""
    if len(api_key) <= 12:
        return api_key[:3] + "***"
    return api_key[:6] + "***" + api_key[-4:]
