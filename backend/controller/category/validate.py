from pydantic import BaseModel
from typing import Optional

class CategoryBase(BaseModel):
    name: str
    code: str
    sort_order: Optional[int] = 0

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    sort_order: Optional[int] = None

class CategoryResponse(CategoryBase):
    id: int
    
    class Config:
        from_attributes = True
