from functools import wraps
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User
from utils.jwt_utils import get_current_user

# 常量定义
ADMIN_ROLE = "admin"
USER_ROLE = "user"

def auth_check(required_roles: list):
    """
    权限检查装饰器
    :param required_roles: 需要的角色列表
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 从kwargs中获取user对象
            user = kwargs.get("current_user")
            if not user:
                # 如果没有user对象，尝试从依赖中获取
                # 注意：这里需要修改，因为装饰器不能直接访问依赖
                # 我们将在路由函数中直接使用依赖
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # 检查用户角色是否在允许的角色列表中
            if user.role not in required_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def check_admin_role(user: User = Depends(get_current_user)):
    """
    检查是否为管理员角色的依赖项
    """
    if user.role != ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action",
        )
    return user
