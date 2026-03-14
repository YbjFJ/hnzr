# 验证码内存存储：邮箱 -> { code, expires_at }，用于忘记密码等，15 分钟有效
import random
import string
from datetime import datetime, timedelta
from typing import Optional

# 邮箱 -> (验证码, 过期时间)
_store: dict[str, tuple[str, datetime]] = {}
CODE_VALID_MINUTES = 15
CODE_LENGTH = 6


def _generate_code() -> str:
    return "".join(random.choices(string.digits, k=CODE_LENGTH))


def set_code(email: str) -> str:
    """为邮箱生成并保存验证码，返回验证码。同一邮箱会覆盖旧码。"""
    code = _generate_code()
    expires = datetime.utcnow() + timedelta(minutes=CODE_VALID_MINUTES)
    _store[email.lower()] = (code, expires)
    return code


def verify_and_consume(email: str, code: str) -> bool:
    """校验验证码是否正确且未过期，通过则删除该记录并返回 True。"""
    key = email.lower()
    if key not in _store:
        return False
    stored_code, expires = _store[key]
    if datetime.utcnow() > expires:
        del _store[key]
        return False
    if stored_code != code.strip():
        return False
    del _store[key]
    return True


def get_expires_at(email: str) -> Optional[datetime]:
    """获取该邮箱当前验证码的过期时间，不存在或已过期返回 None。"""
    key = email.lower()
    if key not in _store:
        return None
    _, expires = _store[key]
    if datetime.utcnow() > expires:
        del _store[key]
        return None
    return expires
