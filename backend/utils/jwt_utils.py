from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User
from config import settings

# OAuth2密码Bearer令牌，使用email作为用户名
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login", auto_error=True)
# 可选认证：无 token 时不报错，用于文章列表等接口按角色区分
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login", auto_error=False)

# 创建JWT令牌
def create_access_token(data: dict):
    """
    创建JWT访问令牌
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# 验证JWT令牌
def decode_access_token(token: str):
    """
    解码并验证JWT令牌
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# 获取当前登录用户
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    从JWT令牌获取当前登录用户
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    # 账号被禁用后，旧 token 在下次请求时失效
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user_optional(token: str = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)):
    """可选认证：无 token 时返回 None；有 token 但无效/过期时抛出 401；有效则返回 User"""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            return None
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None or not user.is_active:
            return None
        return user
    except HTTPException:
        raise
    except Exception:
        return None


def require_admin(current_user: User = Depends(get_current_user)):
    """仅管理员可用的依赖：非管理员返回 403"""
    role_val = getattr(current_user.role, "value", current_user.role)
    if role_val != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可执行此操作",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
