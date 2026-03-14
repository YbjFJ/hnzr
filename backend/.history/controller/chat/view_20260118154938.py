from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse # 引入流式响应
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session
from typing import List, Optional, Generator
import uuid

from database import SessionLocal, get_db
from models import Article, ChatSession, ChatMessage, Favorite, User
from .validate import (
    ChatSessionCreate, ChatSessionUpdate, ChatSessionResponse,
    ChatMessageCreate, ChatMessageResponse, ChatSessionWithLastMessage
)
from utils.jwt_utils import get_current_user
from utils.ai_utils import get_llm
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

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
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
async def stream_chat_message(
    session_id: str, 
    message: ChatMessageCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    user_id = current_user.id
    
    # 1. 验证会话
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # 2. 立即保存用户消息
    user_message = ChatMessage(
        session_id=session_id,
        role=message.role, # 应该是 "user"
        content=message.content,
        ref_article_ids=message.ref_article_ids
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    # ==================== RAG 准备阶段 ====================
    # (保留你原本的 RAG 逻辑，先准备好上下文)
    base_query = message.content
    ref_article_ids_list = []
    context = ""
    
    # 获取相关文章逻辑... (简化展示，保持你原有的查询逻辑)
    search_articles = db.query(Article).filter(
        Article.status == "published",
        Article.title.like(f"%{base_query}%")
    ).limit(5).all()
    
    all_articles = search_articles # 这里简化，请保留你完整的合并去重逻辑
    
    if all_articles:
        from utils.ai_utils import retrieve_relevant_content
        # 假设这是一个同步或异步函数，如果是同步直接调用
        try:
            retrieved_docs = retrieve_relevant_content(base_query, all_articles, k=3)
            if retrieved_docs:
                context += "根据以下相关文章内容，为用户提供回答：\n\n"
                for doc in retrieved_docs:
                    article_id = doc.metadata.get("article_id")
                    if article_id and str(article_id) not in ref_article_ids_list:
                        ref_article_ids_list.append(str(article_id))
                    context += f"【相关内容】:\n{doc.page_content[:300]}...\n\n"
        except ImportError:
            pass # 处理工具未导入情况
            
    # 构建 Prompt
    system_prompt = "你是一个专业的AI咨询助手。"
    if context:
        system_prompt += f"\n{context}\n要求: 基于上下文回答，如果上下文无相关信息，请基于你的知识回答。"
    
    # ==================== 流式生成器 ====================
    async def generate_response():
        # 初始化 LLM (确保开启 streaming=True)
        # 注意：这里需要根据你的实际 utils.ai_utils 修改
        llm = get_llm()
        full_response_content = ""
        
        try:
            # 使用 LangChain 的 stream 方法
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", message.content)
            ])
            chain = prompt_template | llm | StrOutputParser()
            
            # 流式输出
            async for chunk in chain.astream({}):
                full_response_content += chunk
                yield chunk # 直接发送文本片段
                
        except Exception as e:
            err_msg = f"\n[系统错误: 生成回复失败 - {str(e)}]"
            full_response_content += err_msg
            yield err_msg

        # ==================== 生成结束后保存 AI 消息 ====================
        # 注意：yield 结束后，FastAPI 的 db 依赖可能已经关闭
        # 所以我们需要创建一个新的临时会话来写入 AI 消息
        try:
            new_db = SessionLocal() 
            ai_message = ChatMessage(
                session_id=session_id,
                role="ai",
                content=full_response_content,
                ref_article_ids=",".join(ref_article_ids_list) if ref_article_ids_list else None
            )
            new_db.add(ai_message)
            new_db.commit()
            new_db.close()
        except Exception as e:
            print(f"Failed to save AI message: {e}")

    # 返回流式响应
    return StreamingResponse(generate_response(), media_type="text/event-stream")
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
