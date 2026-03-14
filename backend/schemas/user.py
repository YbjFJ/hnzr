from pydantic import BaseModel
from typing import Optional

# Pydantic模型 - 用于请求和响应
class UserBase(BaseModel):
    username: str
    nickname: Optional[str] = None
    role: Optional[str] = "user"

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    
    class Config:
        from_attributes = True
