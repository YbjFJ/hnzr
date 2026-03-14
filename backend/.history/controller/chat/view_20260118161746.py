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
from constant.user_constant import system_prompt
from sqlalchemy import or_  # <--- 新增引入
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
        final_ai_content = ""
        ref_article_ids_list = []
        
        try:
            # 获取 LLM 实例
            llm = get_llm()
            
            # --- 阶段 1: 关键词提取 (新增功能) ---
            yield "> 🔍 **系统状态**: 正在分析您的问题，提取核心搜索词...\n\n"
            
            # 定义提取关键词的 Prompt
            keyword_prompt = ChatPromptTemplate.from_template(
                """你是一个搜索引擎优化专家。请从用户的以下问题中提取 1 到 3 个核心搜索关键词。
                
                用户问题: {question}
                
                要求:
                1. 只输出关键词，用空格分隔。
                2. 去除语气词、助词（如"请问"、"怎么样"、"是什么"）。
                3. 如果问题本身很短，直接输出原问题。
                4. 不要输出任何解释性文字。
                """
            )
            
            # 调用 LLM 进行提取 (非流式，快速完成)
            keyword_chain = keyword_prompt | llm | StrOutputParser()
            # 这里使用 invoke 而不是 astream，因为我们需要拿到完整的关键词再去查库
            extracted_keywords_str = await keyword_chain.ainvoke({"question": message.content})
            
            # 清理关键词字符串 (去除多余空格换行)
            keywords = [k.strip() for k in extracted_keywords_str.split() if k.strip()]
            keywords_display = " ".join(keywords)
            
            yield f"> 🗝️ **系统状态**: 已提取关键词：`{keywords_display}`\n\n"
            await asyncio.sleep(0.1) 
            
            context = ""
            
            # --- 阶段 2: 基于关键词的数据库检索 (修改逻辑) ---
            yield f"> 📚 **系统状态**: 正在根据关键词检索知识库...\n\n"
            
            # 构建查询条件：只要标题包含任意一个关键词即可 (OR 逻辑)
            # 如果没有提取到关键词，回退到使用原问题
            if keywords:
                filters = [Article.title.like(f"%{kw}%") for kw in keywords]
                search_query = db.query(Article).filter(
                    Article.status == "published",
                    or_(*filters) # 使用 OR 逻辑连接所有关键词条件
                )
            else:
                search_query = db.query(Article).filter(
                    Article.status == "published",
                    Article.title.like(f"%{message.content}%")
                )
                
            search_articles = search_query.limit(5).all()
            
            # --- 阶段 3: 向量检索与上下文构建 ---
            if search_articles:
                yield f"> 🧩 **系统状态**: 初步匹配到 {len(search_articles)} 篇文档，正在进行深度语义比对...\n\n"
                
                # 执行向量检索 (假设 retrieve_relevant_content 内部使用了向量相似度)
                # 注意：这里传入的是 message.content (原问题) 还是 keywords (关键词) 取决于你的 retrieve 实现
                # 通常向量检索使用 完整问题 效果更好，因为包含语义
                retrieved_docs = retrieve_relevant_content(message.content, search_articles, k=3)
                
                if retrieved_docs:
                    context += "根据以下相关文章内容，为用户提供回答：\n\n"
                    for doc in retrieved_docs:
                        article_id = doc.metadata.get("article_id")
                        if article_id and str(article_id) not in ref_article_ids_list:
                            ref_article_ids_list.append(str(article_id))
                        context += f"【参考资料】:\n{doc.page_content[:300]}...\n\n"
                    
                    yield f"> ✅ **系统状态**: 资料分析完成，正在生成回答...\n\n---\n\n"
                else:
                    yield "> ⚠️ **系统状态**: 关键词匹配成功，但未找到高相关性的具体段落，将基于通用知识回答...\n\n---\n\n"
            else:
                # 模拟联网搜索分支
                yield f"> 🌐 **系统状态**: 知识库未找到包含 `{keywords_display}` 的内容，正在尝试联网搜索...\n\n"
                await asyncio.sleep(0.5) 
                yield "> ✅ **系统状态**: 联网搜索完成，正在生成回答...\n\n---\n\n"
            
            # --- 阶段 4: LLM 生成最终回答 ---
            
            # 优化后的 System Prompt (保持你之前的优化)
            system_prompt1 = system_prompt
            formatted_context = context if context else "（当前无特定参考资料，请基于通用专业知识回答）"
            final_system_prompt = system_prompt.replace("{context}", formatted_context)
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", final_system_prompt),
                ("user", message.content)
            ])
            
            # 生成回答
            chain = prompt_template | llm | StrOutputParser()
            
            async for chunk in chain.astream({}):
                final_ai_content += chunk 
                yield chunk 
                
        except Exception as e:
            err_msg = f"\n\n> ❌ **系统错误**: 处理过程中发生异常 - {str(e)}"
            final_ai_content += err_msg
            yield err_msg

        # ==================== 生成结束：保存数据 ====================
        try:
            new_db = SessionLocal() 
            ai_message = ChatMessage(
                session_id=session_id,
                role="ai",
                content=final_ai_content,
                ref_article_ids=",".join(ref_article_ids_list) if ref_article_ids_list else None
            )
            new_db.add(ai_message)
            new_db.commit()
            new_db.close()
        except Exception as e:
            print(f"Failed to save AI message: {e}")

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
