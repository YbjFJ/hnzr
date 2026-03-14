from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ArticleBase(BaseModel):
    title: str
    summary: Optional[str] = None
    content: str
    category_id: int
    type: str = "news"
    status: str = "published"
    source_name: Optional[str] = "官方"
    origin_url: Optional[str] = None
    cover_image: Optional[str] = None

class ArticleCreate(ArticleBase):
    pass

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    category_id: Optional[int] = None
    type: Optional[str] = None
    status: Optional[str] = None
    source_name: Optional[str] = None
    origin_url: Optional[str] = None
    cover_image: Optional[str] = None
    is_vectorized: Optional[bool] = None
    view_count: Optional[int] = None
    news_id: Optional[int] = None


class InterpretationCreate(BaseModel):
    """添加官方解读时的请求体：解读内容人工填写"""
    title: str
    summary: Optional[str] = None
    content: str
    category_id: int  # 可与新闻同分类


class GenerateStreamBody(BaseModel):
    """流式生成政策文章请求体"""
    keyword: str = ""
    category_id: int = 0


class ArticleResponse(BaseModel):
    id: int
    title: str
    summary: Optional[str]
    content: str
    category_id: int
    type: str
    status: str
    source_name: str
    origin_url: Optional[str]
    cover_image: Optional[str]
    is_vectorized: bool
    view_count: int
    publish_date: datetime
    news_id: Optional[int] = None

    class Config:
        from_attributes = True
