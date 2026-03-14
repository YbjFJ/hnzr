from fastapi import APIRouter, Depends, HTTPException, StreamingResponse
from fastapi.responses import StreamingResponse # 引入流式响应
from sqlalchemy.orm import Session
from typing import List, Optional, Generator
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

# 发送消息 - 流式输出
@router.post("/sessions/{session_id}/messages/stream")
def send_chat_message_stream(session_id: str, message: ChatMessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    
    # ==================== 优化后的 RAG 流程 ====================
    
    base_query = message.content
    
    # 1. 获取相关文章
    # 1.1 根据关键词搜索文章
    search_articles = db.query(Article).filter(
        Article.status == "published",
        Article.title.like(f"%{base_query}%")
    ).order_by(Article.publish_date.desc()).limit(10).all()
    
    # 1.2 获取用户收藏的文章
    favorite_articles = db.query(Article).join(Favorite).filter(
        Favorite.user_id == user_id,
        Article.status == "published"
    ).order_by(Favorite.created_at.desc()).limit(10).all()
    
    # 1.3 合并文章，去重
    all_articles = list(set(search_articles + favorite_articles))
    
    # 2. 检索相关内容
    context = ""
    ref_article_ids = []
    
    if all_articles:
        from utils.ai_utils import retrieve_relevant_content
        
        # 2.1 从文章中检索相关内容
        retrieved_docs = retrieve_relevant_content(base_query, all_articles, k=3)
        
        # 2.2 构建上下文
        if retrieved_docs:
            context += "根据以下相关文章内容，为用户提供回答：\n\n"
            for doc in retrieved_docs:
                # 提取文章ID
                article_id = doc.metadata.get("article_id")
                if article_id not in ref_article_ids:
                    ref_article_ids.append(str(article_id))
                
                # 添加到上下文
                context += f"【相关内容】:\n{doc.page_content[:500]}...\n\n"
    
    # 3. 构建完整提示词
    prompt = f""
    prompt += f"用户问题: {message.content}\n\n"
    if context:
        prompt += f"{context}\n"
    prompt += f"要求: 基于上述上下文，回答用户问题，提供详细、准确的信息。如果上下文没有相关信息，可以基于你的知识回答。"
    
    # 4. 调用AI生成回复 - 流式输出
    from utils.ai_utils import get_llm
    
    def generate():
        ai_content = ""
        try:
            llm = get_llm(streaming=True)
            
            # 创建AI消息，先保存一个空内容
            ai_message = ChatMessage(
                session_id=session_id,
                role="ai",
                content="",
                ref_article_ids=",".join(ref_article_ids) if ref_article_ids else None
            )
            db.add(ai_message)
            db.commit()
            ai_message_id = ai_message.id
            
            # 流式生成回复
            for chunk in llm.stream(prompt):
                token = chunk.content
                ai_content += token
                yield token
                
                # 每生成一定内容就更新数据库，减少数据库操作次数
                if len(ai_content) % 100 == 0:
                    db.query(ChatMessage).filter(ChatMessage.id == ai_message_id).update({"content": ai_content})
                    db.commit()
            
            # 最后更新完整内容
            db.query(ChatMessage).filter(ChatMessage.id == ai_message_id).update({"content": ai_content})
            db.commit()
        except Exception as e:
            print(f"AI调用失败: {e}")
            error_msg = "抱歉，AI服务暂时不可用，请稍后重试。"
            yield error_msg
            
            # 保存错误消息到数据库
            ai_message = ChatMessage(
                session_id=session_id,
                role="ai",
                content=error_msg
            )
            db.add(ai_message)
            db.commit()
    
    # 返回流式响应
    return StreamingResponse(generate(), media_type="text/event-stream")

# 发送消息 - 非流式（保留原有接口）
@router.post("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
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
    
    # ==================== 优化后的 RAG 流程 ====================
    
    base_query = message.content
    
    # 1. 获取相关文章
    # 1.1 根据关键词搜索文章
    search_articles = db.query(Article).filter(
        Article.status == "published",
        Article.title.like(f"%{base_query}%")
    ).order_by(Article.publish_date.desc()).limit(10).all()
    
    # 1.2 获取用户收藏的文章
    favorite_articles = db.query(Article).join(Favorite).filter(
        Favorite.user_id == user_id,
        Article.status == "published"
    ).order_by(Favorite.created_at.desc()).limit(10).all()
    
    # 1.3 合并文章，去重
    all_articles = list(set(search_articles + favorite_articles))
    
    # 2. 检索相关内容
    context = ""
    ref_article_ids = []
    
    if all_articles:
        from utils.ai_utils import retrieve_relevant_content
        
        # 2.1 从文章中检索相关内容
        retrieved_docs = retrieve_relevant_content(base_query, all_articles, k=3)
        
        # 2.2 构建上下文
        if retrieved_docs:
            context += "根据以下相关文章内容，为用户提供回答：\n\n"
            for doc in retrieved_docs:
                # 提取文章ID
                article_id = doc.metadata.get("article_id")
                if article_id not in ref_article_ids:
                    ref_article_ids.append(str(article_id))
                
                # 添加到上下文
                context += f"【相关内容】:\n{doc.page_content[:500]}...\n\n"
    
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
    
    # 返回整个会话的消息列表
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    return messages

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
