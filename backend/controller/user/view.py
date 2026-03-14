from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from database import get_db
from models import User, UserRole
from .validate import (
    UserCreate,
    UserRegister,
    AdminCreateUser,
    AdminUpdateUser,
    UserLogin,
    UserLoginResponse,
    UserUpdateProfile,
    UserUpdateRole,
    UserUpdatePassword,
    ForgotPasswordRequest,
    ResetPasswordWithCodeRequest,
    UserResponse,
)
from utils.md5_util import Md5Util
from utils.jwt_utils import create_access_token, get_current_user, require_admin
from utils.verify_code_store import set_code, verify_and_consume
from utils.email_util import send_verify_code_email

router = APIRouter(prefix="/users", tags=["users"])


def _role_value(r) -> str:
    return getattr(r, "value", r) if r is not None else ""


# 公开注册（无需登录，角色固定为 user）
@router.post("/register", response_model=UserResponse)
def register(user: UserRegister, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = Md5Util.get_md5_string(user.password)
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        nickname=user.nickname,
        role=UserRole.USER,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# 管理员创建用户（仅管理员）
@router.post("/", response_model=UserResponse)
def create_user(
    user: AdminCreateUser,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = Md5Util.get_md5_string(user.password)
    role_enum = UserRole.ADMIN if user.role == "admin" else UserRole.USER
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        nickname=user.nickname,
        role=role_enum,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# 用户登录
@router.post("/login", response_model=UserLoginResponse)
def login(user: UserLogin, db: Session = Depends(get_db)):
    # 检查邮箱是否存在
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user:
        print('用户不存在')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # 验证密码
    if not Md5Util.check_password(user.password, db_user.hashed_password):
        print('用户密码错误')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # 禁用用户不允许登录
    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员"
        )
    
    # 生成JWT令牌，有效期3天
    access_token = create_access_token(data={"sub": str(db_user.id)})
    
    return UserLoginResponse(
        access_token=access_token,
        user_id=db_user.id,
        email=db_user.email,
        nickname=db_user.nickname,
        role=db_user.role
    )

# 用户登录
# @router.post("/login", response_model=UserLoginResponse)
# def login(
#     # 【修改点1】这里不再接收 JSON (user: UserLogin)，而是接收 OAuth2 表单
#     form_data: OAuth2PasswordRequestForm = Depends(), 
#     db: Session = Depends(get_db)
# ):
#     # 【修改点2】Swagger UI 传过来的是 username 字段，我们把它当作 email 使用
#     input_email = form_data.username
#     input_password = form_data.password

#     # 检查邮箱是否存在
#     db_user = db.query(User).filter(User.email == input_email).first()
#     if not db_user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Incorrect email or password",
#             headers={"WWW-Authenticate": "Bearer"}, # 规范建议加上这个头
#         )
    
#     # 验证密码
#     if not Md5Util.check_password(input_password, db_user.hashed_password):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Incorrect email or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
    
#     # 生成JWT令牌，有效期3天
#     access_token = create_access_token(data={"sub": str(db_user.id)})
    
#     # 【修改点3】返回结果会自动带上 token_type="bearer" (由上面的 response_model 定义)
#     return UserLoginResponse(
#         access_token=access_token,
#         user_id=db_user.id,
#         email=db_user.email,
#         nickname=db_user.nickname,
#         role=db_user.role
#     )

# 获取用户列表（仅管理员，支持关键词搜索）
@router.get("/", response_model=List[UserResponse])
def get_users(
    skip: int = 0,
    limit: int = 100,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    q = db.query(User)
    if keyword and keyword.strip():
        k = f"%{keyword.strip()}%"
        q = q.filter(or_(User.email.ilike(k), User.nickname.ilike(k)))
    users = q.offset(skip).limit(limit).all()
    return users

# 获取单个用户（本人或管理员）
@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    role_val = _role_value(current_user.role)
    if current_user.id != user_id and role_val != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看其他用户")
    return db_user

# 用户更新个人资料（本人可改自己，管理员可改任意）
@router.put("/{user_id}/profile", response_model=UserResponse)
def update_user_profile(
    user_id: int,
    user_update: UserUpdateProfile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    role_val = _role_value(current_user.role)
    if current_user.id != user_id and role_val != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可修改其他用户资料")
    if user_update.nickname is not None:
        db_user.nickname = user_update.nickname
    if user_update.avatar is not None:
        db_user.avatar = user_update.avatar
    db.commit()
    db.refresh(db_user)
    return db_user

# 管理员更新用户（角色、昵称、头像、是否激活、新密码）
@router.put("/{user_id}/admin", response_model=UserResponse)
def admin_update_user(
    user_id: int,
    body: AdminUpdateUser,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if body.nickname is not None:
        db_user.nickname = body.nickname
    if body.avatar is not None:
        db_user.avatar = body.avatar
    if body.role is not None:
        db_user.role = UserRole.ADMIN if body.role == "admin" else UserRole.USER
    # 明确更新 is_active（包括设为 False/禁用），确保数据库写入
    if body.is_active is not None:
        db_user.is_active = bool(body.is_active)
    if body.new_password is not None:
        db_user.hashed_password = Md5Util.get_md5_string(body.new_password)
    db.commit()
    db.refresh(db_user)
    return db_user

# 管理员更新用户角色（保留兼容）
@router.put("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    role_update: UserUpdateRole,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    db_user.role = UserRole.ADMIN if role_update.role == "admin" else UserRole.USER
    db.commit()
    db.refresh(db_user)
    return db_user

# 忘记密码：发送验证码到邮箱（15 分钟有效）
@router.post("/forgot-password/send-code")
def forgot_password_send_code(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == body.email).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="该邮箱未注册")
    code = set_code(body.email)
    ok = send_verify_code_email(body.email, code, valid_minutes=15)
    if not ok:
        raise HTTPException(status_code=500, detail="发送验证码失败，请稍后重试")
    return {"message": "验证码已发送至您的邮箱，15 分钟内有效。"}

# 忘记密码：凭验证码重置密码
@router.post("/forgot-password/reset")
def forgot_password_reset(body: ResetPasswordWithCodeRequest, db: Session = Depends(get_db)):
    if not verify_and_consume(body.email, body.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期，请重新获取")
    db_user = db.query(User).filter(User.email == body.email).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    db_user.hashed_password = Md5Util.get_md5_string(body.new_password)
    db.commit()
    db.refresh(db_user)
    return {"message": "密码已重置，请使用新密码登录。"}

# 用户更新密码（仅本人，需验证旧密码）
@router.put("/{user_id}/password", response_model=UserResponse)
def update_user_password(
    user_id: int,
    password_update: UserUpdatePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="只能修改自己的密码")
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not Md5Util.check_password(password_update.old_password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    db_user.hashed_password = Md5Util.get_md5_string(password_update.new_password)
    db.commit()
    db.refresh(db_user)
    return db_user

# 删除用户（仅管理员）
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    return {"message": "User deleted successfully"}
