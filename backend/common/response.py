from pydantic import BaseModel
from typing import Any, Optional

class BaseResponse(BaseModel):
    """基础响应模型"""
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None

class ApiResponse(BaseResponse):
    """API响应模型"""
    pass

class ErrorResponse(BaseModel):
    """错误响应模型"""
    code: int
    message: str
