from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# 聊天会话相关模型
class ChatSessionBase(BaseModel):
    title: Optional[str] = None

class ChatSessionCreate(ChatSessionBase):
    pass

class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None

class ChatSessionResponse(BaseModel):
    id: str
    user_id: int
    title: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

# 聊天消息相关模型
class ChatMessageBase(BaseModel):
    content: str
    ref_article_ids: Optional[str] = None

class ChatMessageCreate(ChatMessageBase):
    role: str  # user | ai

class ChatMessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    ref_article_ids: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

# 会话列表响应
class ChatSessionWithLastMessage(ChatSessionResponse):
    last_message: Optional[str] = None
    message_count: int = 0
