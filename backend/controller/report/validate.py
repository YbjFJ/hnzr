from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ReportBase(BaseModel):
    title: str
    content: str
    ref_ids: List[int]  # 引用的文章ID列表

class ReportCreate(ReportBase):
    pass

class ReportUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    user_note: Optional[str] = None
    is_archived: Optional[bool] = None

class ReportResponse(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    reference_article_ids: str
    user_note: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
