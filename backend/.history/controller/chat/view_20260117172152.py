from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from database import get_db
from models import Article, ChatSession, ChatMessage, Favorite, User
from .validate import (
    ChatSessionCreate, ChatSessionUpdate, ChatSessionResponse,
    ChatMessageCreate, ChatMessageResponse, ChatSessionWithLastMessage
)
from utils.jwt_utils import get_current_user

router = APIRouter(prefix="/chats", tags=["chats"])

# 获取聊天会话列表
@router.get("/sessions", response_model=List[ChatSessionWithLastMessage])
def get_chat_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    # 获取所有会话
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == user_id
    ).order_by(ChatSession.created_at.desc()).all()
    
    # 构建响应，包含最后一条消息和消息数量
    result = []
    for session in sessions:
        # 获取最后一条消息
        last_message = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at.desc()).first()
        
        # 获取消息数量
        message_count = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).count()
        
        # 构建响应对象
        session_data = ChatSessionResponse.model_validate(session)
        session_with_last = ChatSessionWithLastMessage(
            **session_data.model_dump(),
            last_message=last_message.content if last_message else None,
            message_count=message_count
        )
        result.append(session_with_last)
    
    return result

# 创建聊天会话
@router.post("/sessions", response_model=ChatSessionResponse)
def create_chat_session(session: ChatSessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    # 生成UUID作为会话ID
    session_id = str(uuid.uuid4())
    
    # 创建会话
    db_session = ChatSession(
        id=session_id,
        user_id=user_id,
        title=session.title
    )
    
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    
    return db_session

# 获取单个会话
@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
def get_chat_session(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    return session

# 更新会话
@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
def update_chat_session(session_id: str, session: ChatSessionUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    db_session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    
    if not db_session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # 更新字段
    if session.title is not None:
        db_session.title = session.title
    
    db.commit()
    db.refresh(db_session)
    
    return db_session

# 删除会话
@router.delete("/sessions/{session_id}")
def delete_chat_session(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    db.delete(session)
    db.commit()
    
    return {"message": "Chat session deleted successfully"}

# 获取会话消息列表
@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
def get_chat_messages(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    # 检查会话是否属于该用户
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # 获取消息列表
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    return messages

# 发送消息
@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
def send_chat_message(session_id: str, message: ChatMessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    # 检查会话是否属于该用户
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # 创建用户消息
    user_message = ChatMessage(
        session_id=session_id,
        role=message.role,
        content=message.content,
        ref_article_ids=message.ref_article_ids
    )
    
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    # ==================== RAG 流程 ====================
    
    # 1. 提取关键词（这里简单处理，使用用户消息作为关键词）
    keywords = message.content
    
    # 2. 根据关键词搜索文章
    search_articles = db.query(Article).filter(
        Article.status == "published",
        Article.title.like(f"%{keywords}%")
    ).order_by(Article.publish_date.desc()).limit(5).all()
    
    # 3. 获取用户收藏的文章
    favorite_articles = db.query(Article).join(Favorite).filter(
        Favorite.user_id == user_id,
        Article.status == "published"
    ).order_by(Favorite.created_at.desc()).limit(5).all()
    
    # 4. 合并文章，去重
    all_articles = list(set(search_articles + favorite_articles))
    
    # 5. 构建上下文
    context = ""
    ref_article_ids = []
    
    if all_articles:
        context += "根据以下相关文章，为用户提供回答：\n\n"
        for article in all_articles:
            context += f"文章ID: {article.id}\n"
            context += f"标题: {article.title}\n"
            context += f"摘要: {article.summary if article.summary else '无'}\n"
            context += f"内容: {article.content[:300]}...\n\n"
            ref_article_ids.append(str(article.id))
    
    # 6. 构建完整提示词
    prompt = f""
    prompt += f"用户问题: {message.content}\n\n"
    if context:
        prompt += f"{context}\n"
    prompt += f"要求: 基于上述上下文，回答用户问题，提供详细、准确的信息。如果上下文没有相关信息，可以基于你的知识回答。"
    
    # 7. 调用ChatOpenAI生成回复
    from utils.ai_utils import get_llm
    
    try:
        llm = get_llm()
        ai_response = llm.invoke(prompt)
        ai_content = ai_response.content
    except Exception as e:
        print(f"AI调用失败: {e}")
        ai_content = "抱歉，AI服务暂时不可用，请稍后重试。"
    
    # 8. 创建AI回复消息
    ai_message = ChatMessage(
        session_id=session_id,
        role="ai",
        content=ai_content,
        ref_article_ids=",".join(ref_article_ids) if ref_article_ids else None
    )
    
    db.add(ai_message)
    db.commit()
    db.refresh(ai_message)
    
    return ai_message

# 删除消息
@router.delete("/messages/{message_id}")
def delete_chat_message(message_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    # 查找消息并检查所属会话是否属于该用户
    message = db.query(ChatMessage).join(ChatSession).filter(
        ChatMessage.id == message_id,
        ChatSession.user_id == user_id
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    db.delete(message)
    db.commit()
    
    return {"message": "Message deleted successfully"}
