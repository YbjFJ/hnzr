from enum import Enum

class ArticleTypeEnum(Enum):
    """文章类型枚举"""
    NEWS = "news"  # 外部新闻
    INTERPRETATION = "interpretation"  # 独家解读

class ArticleStatusEnum(Enum):
    """文章状态枚举"""
    DRAFT = "draft"  # 草稿
    PUBLISHED = "published"  # 发布
    OFFLINE = "offline"  # 下架

class UserRoleEnum(Enum):
    """用户角色枚举"""
    ADMIN = "admin"  # 管理员
    USER = "user"  # 普通用户
