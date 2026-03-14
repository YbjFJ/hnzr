from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import datetime

# 定义允许的用户角色
UserRoleType = Literal["user", "admin"]

class UserBase(BaseModel):
    email: EmailStr
    nickname: Optional[str] = None
    role: Optional[UserRoleType] = "user"

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="密码长度不能少于6位")


# 公开注册（不允许指定 role，固定为 user）
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="密码长度不能少于6位")
    nickname: Optional[str] = None


# 管理员创建用户（可指定 role）
class AdminCreateUser(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="密码长度不能少于6位")
    nickname: Optional[str] = None
    role: UserRoleType = "user"


# 管理员批量更新用户（昵称、头像、角色、是否激活、新密码）
class AdminUpdateUser(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[UserRoleType] = None
    is_active: Optional[bool] = None
    new_password: Optional[str] = Field(None, min_length=6, description="新密码（仅管理员可直接设置）")

# 登录请求模型
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# 登录响应模型
class UserLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    nickname: Optional[str]
    role: str

# 用户更新个人资料（nickname和avatar）
class UserUpdateProfile(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None

# 管理员更新用户角色
class UserUpdateRole(BaseModel):
    role: UserRoleType = Field(..., description="用户角色只能是user或admin")

# 用户更新密码
class UserUpdatePassword(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, description="新密码长度不能少于6位")

# 忘记密码：发送验证码（仅需邮箱）
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

# 忘记密码：凭验证码重置（邮箱 + 验证码 + 新密码）
class ResetPasswordWithCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=8, description="验证码")
    new_password: str = Field(..., min_length=6, description="新密码长度不能少于6位")

class UserResponse(BaseModel):
    id: int
    email: str
    nickname: Optional[str]
    role: str
    is_active: bool
    avatar: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
