from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    Text, 
    DateTime, 
    Boolean, 
    ForeignKey, 
    Enum,
    func
)
from sqlalchemy.orm import relationship
from database import Base
import enum

# ==========================================
# 1. 枚举类型定义 (Enums)
# ==========================================

class UserRole(str, enum.Enum):
    USER = "user"       # 普通用户
    ADMIN = "admin"     # 管理员 (可爬虫、发解读)

class ArticleType(str, enum.Enum):
    NEWS = "news"                   # 外部抓取的新闻
    INTERPRETATION = "interpretation" # 平台独家解读

class ArticleStatus(str, enum.Enum):
    DRAFT = "draft"         # 草稿
    PUBLISHED = "published" # 已发布
    OFFLINE = "offline"     # 下架

# ==========================================
# 2. 用户中心模块 (User System)
# ==========================================

class User(Base):
    """
    用户表：存储基本信息和权限
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False, comment="登录邮箱/账号")
    hashed_password = Column(String(255), nullable=False, comment="加密后的密码")
    
    nickname = Column(String(50), comment="用户昵称")
    avatar = Column(String(255), comment="头像URL")
    
    # 权限控制
    role = Column(Enum(UserRole), default=UserRole.USER, comment="角色")
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联关系
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user")
    reports = relationship("AnalysisReport", back_populates="user")


# ==========================================
# 3. 内容管理模块 (CMS: News & Interpretations)
# ==========================================

class Category(Base):
    """
    分类表：如 宏观、金融、地产、科技
    """
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, comment="分类名称")
    code = Column(String(50), unique=True, comment="分类编码(用于前端路由),如 macro")
    sort_order = Column(Integer, default=0, comment="排序权重，越大越靠前")
    
    # 关联关系
    articles = relationship("Article", back_populates="category")


class Article(Base):
    """
    文章表：核心内容库
    包括：网上抓取的新闻 + 内部发布的解读
    """
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    
    # 基础内容
    title = Column(String(255), nullable=False, index=True, comment="标题")
    summary = Column(String(500), comment="摘要(列表页展示)")
    content = Column(Text, nullable=False, comment="文章正文(HTML或Markdown)")
    cover_image = Column(String(255), comment="封面图URL")
    
    # 分类与类型
    category_id = Column(Integer, ForeignKey("categories.id"))
    type = Column(Enum(ArticleType), default=ArticleType.NEWS, index=True, comment="文章类型：新闻/解读")
    status = Column(Enum(ArticleStatus), default=ArticleStatus.PUBLISHED, comment="发布状态")
    
    # 来源信息 (爬虫用)
    source_name = Column(String(100), default="官方", comment="来源：如央行官网、财新")
    origin_url = Column(String(500), comment="原始链接(方便回溯)")
    publish_date = Column(DateTime, default=func.now(), comment="新闻发布时间")
    
    # RAG 向量化状态
    is_vectorized = Column(Boolean, default=False, comment="是否已存入向量数据库")

    # 统计数据
    view_count = Column(Integer, default=0, comment="阅读量")

    # 关联关系
    category = relationship("Category", back_populates="articles")
    favorited_by = relationship("Favorite", back_populates="article")


class Favorite(Base):
    """
    收藏表：用户收藏了哪些文章
    """
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    article_id = Column(Integer, ForeignKey("articles.id"))
    created_at = Column(DateTime, server_default=func.now())

    # 关联关系
    user = relationship("User", back_populates="favorites")
    article = relationship("Article", back_populates="favorited_by")


# ==========================================
# 4. AI 互动与咨询模块 (RAG & Chat)
# ==========================================

class ChatSession(Base):
    """
    会话表：左侧的聊天历史列表
    """
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, comment="UUID") # 建议使用UUID
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(100), comment="会话标题(自动生成或用户修改)")
    created_at = Column(DateTime, server_default=func.now())
    
    # 关联关系
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """
    消息表：具体的问答记录
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"))
    
    role = Column(String(20), comment="user | ai")
    content = Column(Text, comment="聊天内容")
    
    # 【核心】上下文引用
    # 记录该次回答引用了哪些文章ID，格式如 "1,5,12"
    ref_article_ids = Column(String(255), nullable=True, comment="引用的文章ID列表")
    
    created_at = Column(DateTime, server_default=func.now())
    
    # 关联关系
    session = relationship("ChatSession", back_populates="messages")


# ==========================================
# 5. 咨询成果沉淀模块 (Reports)
# ==========================================

class AnalysisReport(Base):
    """
    咨询报告表：用户保存的深度分析结果
    区别于随意的聊天记录，这是用户想要归档的“成果”
    """
    __tablename__ = "analysis_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    title = Column(String(100), comment="报告标题")
    content = Column(Text, comment="AI生成的深度分析报告内容")
    
    # 记录生成该报告时，用户选择了哪些文章作为依据
    reference_article_ids = Column(String(255), comment="引用的文章ID列表(如: 1,5,12)")
    
    # 用户对这份报告的个性化处理
    user_note = Column(String(500), comment="用户备注/心得")
    is_archived = Column(Boolean, default=False, comment="是否星标/归档")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # 关联关系
    user = relationship("User", back_populates="reports")
