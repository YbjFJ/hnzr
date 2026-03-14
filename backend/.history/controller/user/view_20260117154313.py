from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import User
from .validate import (
    UserCreate, 
    UserUpdateProfile, 
    UserUpdateRole, 
    UserUpdatePassword,
    UserResponse
)
from utils.md5_util import Md5Util
from utils.auth import auth_check, ADMIN_ROLE, get_current_user

router = APIRouter(prefix="/users", tags=["users"])

# 创建用户
@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # 检查邮箱是否已存在
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # 创建新用户，使用MD5加密密码
    hashed_password = Md5Util.get_md5_string(user.password)
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        nickname=user.nickname,
        role=user.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

# 获取用户列表
@router.get("/", response_model=List[UserResponse])
def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(User).offset(skip).limit(limit).all()
    return users

# 获取单个用户
@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

# 用户更新个人资料（nickname和avatar）
@router.put("/{user_id}/profile", response_model=UserResponse)
def update_user_profile(user_id: int, user_update: UserUpdateProfile, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 更新字段
    if user_update.nickname is not None:
        db_user.nickname = user_update.nickname
    if user_update.avatar is not None:
        db_user.avatar = user_update.avatar
    
    db.commit()
    db.refresh(db_user)
    
    return db_user

# 管理员更新用户角色
@router.put("/{user_id}/role", response_model=UserResponse)
def update_user_role(user_id: int, role_update: UserUpdateRole, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 更新角色
    db_user.role = role_update.role
    
    db.commit()
    db.refresh(db_user)
    
    return db_user

# 用户更新密码
@router.put("/{user_id}/password", response_model=UserResponse)
def update_user_password(user_id: int, password_update: UserUpdatePassword, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 验证旧密码是否正确
    if not Md5Util.check_password(password_update.old_password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    
    # 更新密码，使用MD5加密
    db_user.hashed_password = Md5Util.get_md5_string(password_update.new_password)
    
    db.commit()
    db.refresh(db_user)
    
    return db_user

# 删除用户（只有管理员可以操作）
@router.delete("/{user_id}")
@auth_check(required_roles=[ADMIN_ROLE])
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    
    return {"message": "User deleted successfully"}
