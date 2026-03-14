import asyncio
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models import Article, ArticleStatus, Category, Favorite, User
import json
from utils.ai_utils import generate_article_from_search, get_llm, generate_article_from_search_stream
from utils.jwt_utils import get_current_user, get_current_user_optional
from .validate import ArticleCreate, ArticleUpdate, ArticleResponse, InterpretationCreate, GenerateStreamBody

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/articles", tags=["articles"])

# 获取文章列表（普通用户仅能看到已发布；管理员可看全部状态）
@router.get("/", response_model=List[ArticleResponse])
def get_articles(
    skip: int = 0,
    limit: int = 20,
    category_id: Optional[int] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    sort_by: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    query = db.query(Article)
    
    # 判断是否管理员（兼容 role 为枚举或字符串）
    is_admin = False
    if current_user and current_user.role is not None:
        role_val = getattr(current_user.role, "value", current_user.role)
        if hasattr(role_val, "value"):
            role_val = role_val.value
        is_admin = str(role_val).lower() == "admin"
    
    # 非管理员只能看已发布；管理员则按传入的 status 筛选（含草稿/已发布/已下线）
    if not is_admin:
        status = "published"
    
    # 筛选条件
    if category_id:
        query = query.filter(Article.category_id == category_id)
    if type:
        query = query.filter(Article.type == type)
    if status and status in ("draft", "published", "offline"):
        query = query.filter(Article.status == ArticleStatus(status))
    elif not is_admin:
        query = query.filter(Article.status == ArticleStatus.PUBLISHED)
    # 管理员且 status 为空时不过滤状态，显示全部
    if keyword and keyword.strip():
        kw = keyword.strip()
        # 支持按标题或摘要模糊搜索（摘要为 NULL 时只匹配标题）
        query = query.filter(
            or_(
                Article.title.like(f"%{kw}%"),
                and_(Article.summary.isnot(None), Article.summary.like(f"%{kw}%")),
            )
        )
    
    # 排序：sort_by=views 按浏览数降序（同浏览数按发布时间降序），默认按发布时间降序
    if sort_by == "views":
        query = query.order_by(Article.view_count.desc(), Article.publish_date.desc())
    else:
        query = query.order_by(Article.publish_date.desc())
    articles = query.offset(skip).limit(limit).all()

    return articles

# 搜索文章（用于RAG）
@router.get("/search", response_model=List[ArticleResponse])
def search_articles(
    keyword: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    根据关键词搜索文章，用于RAG功能
    """
    query = db.query(Article)
    
    # 只搜索已发布的文章
    query = query.filter(Article.status == "published")
    
    # 关键词搜索（标题模糊匹配）
    query = query.filter(Article.title.like(f"%{keyword}%"))
    
    # 排序：按照发布时间倒序，取最近的文章
    articles = query.order_by(Article.publish_date.desc()).limit(limit).all()
    
    return articles


# 获取某篇新闻下的所有官方解读（普通用户与管理员均可，仅返回已发布）
@router.get("/{news_id}/interpretations", response_model=List[ArticleResponse])
def get_interpretations(
    news_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    news = db.query(Article).filter(Article.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")
    query = (
        db.query(Article)
        .filter(Article.news_id == news_id, Article.type == "interpretation")
        .order_by(Article.publish_date.desc())
    )
    is_admin = False
    if current_user:
        role_val = getattr(current_user.role, "value", current_user.role)
        is_admin = role_val == "admin"
    if not is_admin:
        query = query.filter(Article.status == "published")
    return query.all()


# 管理员：为某篇新闻添加官方解读（人工填写内容）
@router.post("/{news_id}/interpretations", response_model=ArticleResponse)
def add_interpretation(
    news_id: int,
    body: InterpretationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role_val = getattr(current_user.role, "value", current_user.role)
    if role_val != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可添加官方解读")
    news = db.query(Article).filter(Article.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")
    if news.type != "news":
        raise HTTPException(status_code=400, detail="只能为新闻类文章添加解读")
    category = db.query(Category).filter(Category.id == body.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="分类不存在")
    db_article = Article(
        title=body.title,
        summary=body.summary or "",
        content=body.content,
        category_id=body.category_id,
        type="interpretation",
        status="published",
        source_name="官方解读",
        news_id=news_id,
    )
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article


# 管理员：AI 流式生成解读正文（根据当前新闻内容）
@router.post("/{news_id}/interpretations/generate-stream")
async def generate_interpretation_stream(
    news_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role_val = getattr(current_user.role, "value", current_user.role)
    if role_val != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可使用 AI 生成解读")
    news = db.query(Article).filter(Article.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")
    if getattr(news.type, "value", news.type) != "news":
        raise HTTPException(status_code=400, detail="只能为新闻类文章生成解读")

    INTERPRETATION_PROMPT = """你是一位政策与新闻解读专家。请根据下面这篇新闻，生成「官方解读」的标题、摘要和正文，并严格按照以下格式输出（必须包含三块标记，顺序不可调换）：

##TITLE##
这里写一行解读标题，简洁有力，不超过 30 字

##SUMMARY##
这里写 1～3 句话的摘要，用于列表页展示，约 80～150 字

##BODY##
正文使用 Markdown 格式，便于后续渲染美观。要求：
- 使用二级标题（## 背景说明、## 要点提炼、## 影响与建议 等）划分小节
- 要点用列表：- 或 1. 2. 3.
- 关键术语用 **加粗**
- 段落之间空一行
- 语言正式、客观，正文约 300～600 字

新闻标题：
{title}

新闻摘要：
{summary}

新闻正文：
{content}

请严格按 ##TITLE## / ##SUMMARY## / ##BODY## 三块输出，不要输出其他说明文字："""

    async def generate_response():
        try:
            title = news.title or ""
            summary = (news.summary or "")[:800]
            content = (news.content or "")[:3000]
            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("user", INTERPRETATION_PROMPT),
            ])
            chain = prompt | llm | StrOutputParser()
            async for chunk in chain.astream({"title": title, "summary": summary, "content": content}):
                if chunk:
                    yield chunk
        except Exception as e:
            yield f"\n\n> 生成异常: {str(e)}"

    return StreamingResponse(generate_response(), media_type="text/event-stream")


# 获取文章详情
@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # 增加阅读量
    article.view_count += 1
    db.commit()
    db.refresh(article)
    
    return article

# 创建文章
@router.post("/", response_model=ArticleResponse)
def create_article(article: ArticleCreate, db: Session = Depends(get_db)):
    # 检查分类是否存在
    category = db.query(Category).filter(Category.id == article.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Category not found")
    
    # 创建文章
    db_article = Article(**article.model_dump())
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    
    return db_article



@router.post("/generate-stream")
async def generate_article_stream(
    body: GenerateStreamBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式生成：先推送步骤文案，最后推送 [DONE]article_id"""
    keyword = (body.keyword or "").strip()
    category_id = body.category_id
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    async def stream():
        async for chunk in generate_article_from_search_stream(keyword):
            if chunk.startswith("[ERROR]"):
                yield chunk
                return
            if chunk.startswith("[ARTICLE_JSON]"):
                try:
                    data = json.loads(chunk[14:].strip())
                    urls = data.get("source_urls", [])
                    origin_url_str = "\n".join(urls) if urls else ""
                    db_article = Article(
                        title=data["title"],
                        summary=data.get("summary", ""),
                        content=data["content"],
                        category_id=category_id,
                        type="news",
                        status="draft",
                        source_name="AI智能简报",
                        origin_url=origin_url_str,
                        is_vectorized=False,
                    )
                    db.add(db_article)
                    db.commit()
                    db.refresh(db_article)
                    yield "文章已保存\n"
                    yield f"[DONE]{db_article.id}\n"
                except Exception as e:
                    yield f"[ERROR] 保存失败: {str(e)}\n"
                return
            yield chunk

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/generate", response_model=ArticleResponse)
async def generate_article(
    keyword: str,
    category_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    通过网络搜索和AI总结自动生成高质量新闻咨询
    """
    # 1. 验证输入
    if not keyword.strip():
        raise HTTPException(status_code=400, detail="关键词不能为空")

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    # 2. 调用生成逻辑
    generated_data = await generate_article_from_search(keyword)
    
    if not generated_data:
        raise HTTPException(status_code=502, detail="文章生成服务暂时不可用或未找到相关内容")
    
    # === 新增：处理 URL 列表 ===
    # 获取 URL 列表，默认为空列表
    urls = generated_data.get("source_urls", [])
    
    # 将列表转换为字符串存入数据库
    # 方式 A：用换行符分隔（清晰，适合长文本字段）
    origin_url_str = "\n".join(urls) 

    # 3. 数据库操作
    try:
        db_article = Article(
            title=generated_data["title"],
            summary=generated_data["summary"],
            content=generated_data["content"],
            category_id=category_id,
            type="news",
            status="draft",
            source_name="AI智能简报",
            
            # === 修改这里 ===
            origin_url=origin_url_str,  # 填入处理好的 URL 字符串
            # ===============
            
            is_vectorized=False,
            # author_id=current_user.id 
        )
        
        db.add(db_article)
        db.commit()
        db.refresh(db_article)
        
        return db_article

    except Exception as e:
        db.rollback()
        logger.error(f"数据库保存失败: {str(e)}")
        raise HTTPException(status_code=500, detail="文章保存失败")

# 更新文章
@router.put("/{article_id}", response_model=ArticleResponse)
def update_article(article_id: int, article: ArticleUpdate, db: Session = Depends(get_db)):
    db_article = db.query(Article).filter(Article.id == article_id).first()
    if not db_article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # 检查分类是否存在（如果更新了分类）
    if article.category_id:
        category = db.query(Category).filter(Category.id == article.category_id).first()
        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
    
    # 更新字段
    update_data = article.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_article, field, value)
    
    db.commit()
    db.refresh(db_article)
    
    return db_article

# 删除文章
@router.delete("/{article_id}")
def delete_article(article_id: int, db: Session = Depends(get_db)):
    db_article = db.query(Article).filter(Article.id == article_id).first()
    if not db_article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    db.delete(db_article)
    db.commit()
    
    return {"message": "Article deleted successfully"}

# 发布文章
@router.put("/{article_id}/publish")
def publish_article(article_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_article = db.query(Article).filter(Article.id == article_id).first()
    if not db_article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    db_article.status = "published"
    db.commit()
    db.refresh(db_article)
    
    return db_article

# 下线文章
@router.put("/{article_id}/offline")
def offline_article(article_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_article = db.query(Article).filter(Article.id == article_id).first()
    if not db_article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    db_article.status = "offline"
    db.commit()
    db.refresh(db_article)
    
    return db_article

# 转为草稿
@router.put("/{article_id}/draft")
def draft_article(article_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_article = db.query(Article).filter(Article.id == article_id).first()
    if not db_article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    db_article.status = "draft"
    db.commit()
    db.refresh(db_article)
    
    return db_article

# 收藏文章
@router.post("/{article_id}/favorite")
def favorite_article(article_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    # 检查文章是否存在
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # 检查是否已经收藏
    existing_favorite = db.query(Favorite).filter(
        Favorite.user_id == user_id,
        Favorite.article_id == article_id
    ).first()
    
    if existing_favorite:
        raise HTTPException(status_code=400, detail="Article already favorited")
    
    # 创建收藏
    favorite = Favorite(user_id=user_id, article_id=article_id)
    db.add(favorite)
    db.commit()
    
    return {"message": "Article favorited successfully"}

# 取消收藏
@router.delete("/{article_id}/favorite")
def unfavorite_article(article_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    # 查找收藏记录
    favorite = db.query(Favorite).filter(
        Favorite.user_id == user_id,
        Favorite.article_id == article_id
    ).first()
    
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    db.delete(favorite)
    db.commit()
    
    return {"message": "Article unfavorited successfully"}

# 检查文章是否已收藏
@router.get("/{article_id}/favorite")
def check_favorite(article_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    
    # 检查是否已经收藏
    existing_favorite = db.query(Favorite).filter(
        Favorite.user_id == user_id,
        Favorite.article_id == article_id
    ).first()
    
    return {"is_favorite": existing_favorite is not None}
