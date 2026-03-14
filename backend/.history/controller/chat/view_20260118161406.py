import asyncio
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
from utils.ai_utils import get_llm, retrieve_relevant_content
from constant.
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
        role=message.role,
        content=message.content,
        ref_article_ids=message.ref_article_ids
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    # ==================== 定义流式生成器 ====================
    async def generate_response():
        # 用于收集最终的纯净 AI 回复，存入数据库
        final_ai_content = ""
        # 用于收集引用文章ID
        ref_article_ids_list = []
        
        try:
            # --- 阶段 1: 发送状态提示 ---
            # 这里的 \n\n 是为了让前端 Markdown 渲染时换行
            yield "> 🔍 **系统状态**: 正在分析您的问题关键词...\n\n"
            await asyncio.sleep(0.2) # 稍微停顿，让用户看清提示(可选)
            
            base_query = message.content
            context = ""
            
            # --- 阶段 2: 数据库检索 ---
            yield f"> 📚 **系统状态**: 正在检索知识库：'{base_query[:10]}...' \n\n"
            
            # 注意：将耗时的查询逻辑移到了这里
            # 在 Fastapi 中，如果使用同步 ORM，这里可能会阻塞一小会儿，但在 StreamingResponse 中是可以接受的
            search_articles = db.query(Article).filter(
                Article.status == "published",
                Article.title.like(f"%{base_query}%")
            ).limit(5).all()
            
            all_articles = search_articles # 这里可以加入你的收藏夹逻辑
            
            # --- 阶段 3: 向量检索与上下文构建 ---
            if all_articles:
                yield f"> 🧩 **系统状态**: 初步找到 {len(all_articles)} 篇相关文章，正在进行深度内容匹配...\n\n"
                
                # 执行向量检索
                retrieved_docs = retrieve_relevant_content(base_query, all_articles, k=3)
                
                if retrieved_docs:
                    context += "根据以下相关文章内容，为用户提供回答：\n\n"
                    for doc in retrieved_docs:
                        article_id = doc.metadata.get("article_id")
                        if article_id and str(article_id) not in ref_article_ids_list:
                            ref_article_ids_list.append(str(article_id))
                        context += f"【相关内容】:\n{doc.page_content[:300]}...\n\n"
                    
                    yield f"> ✅ **系统状态**: 已提取关键信息，正在生成回答...\n\n---\n\n"
                else:
                    yield "> ⚠️ **系统状态**: 文章中未匹配到具体段落，尝试使用通用知识回答...\n\n---\n\n"
            else:
                # 模拟联网搜索分支
                yield "> 🌐 **系统状态**: 本地知识库未找到相关内容，正在尝试联网搜索(模拟)...\n\n"
                await asyncio.sleep(0.5) 
                yield "> ✅ **系统状态**: 搜索完成，正在生成回答...\n\n---\n\n"
            
            # --- 阶段 4: LLM 生成 ---
            # 构建 Prompt
            # 优化后的 System Prompt

            # 填充上下文，如果为空则提示无上下文
            formatted_context = context if context else "（当前无特定参考资料，请基于通用专业知识回答）"
            system_prompt = constant.
            # 替换 prompt 中的占位符
            final_system_prompt = system_prompt.replace("{context}", formatted_context)
            llm = get_llm() # 确保你的 get_llm() 返回的是 streaming=True 的实例
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", final_system_prompt),
                ("user", message.content)
            ])
            chain = prompt_template | llm | StrOutputParser()
            
            # 开始流式输出真正的答案
            async for chunk in chain.astream({}):
                final_ai_content += chunk # 收集纯净内容用于存储
                yield chunk # 发送给前端显示
                
        except Exception as e:
            err_msg = f"\n\n> ❌ **系统错误**: 处理过程中发生异常 - {str(e)}"
            final_ai_content += err_msg
            yield err_msg

        # ==================== 生成结束：保存数据 ====================
        # 关键点：我们重新开启一个数据库会话，因为之前的 db session 可能在 request 结束时有些问题
        # 并且，我们只保存 final_ai_content，不保存上面的 "> System Status" 废话
        try:
            new_db = SessionLocal() 
            ai_message = ChatMessage(
                session_id=session_id,
                role="ai",
                content=final_ai_content, # 存入数据库的是干净的回答
                ref_article_ids=",".join(ref_article_ids_list) if ref_article_ids_list else None
            )
            new_db.add(ai_message)
            new_db.commit()
            new_db.close()
            print("AI response saved to DB successfully.")
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
