from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import Favorite, Article
from utils.jwt_utils import get_current_user
from models import User
from controller.article.validate import ArticleResponse

router = APIRouter(prefix="/favorites", tags=["favorites"])

# 获取用户收藏列表
@router.get("/")
def get_favorites(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_id = current_user.id
    
    # 计算偏移量
    skip = (page - 1) * page_size
    
    # 查询用户的收藏记录，包含文章详情
    favorites_query = db.query(Favorite).filter(Favorite.user_id == user_id)
    
    # 获取总记录数
    total = favorites_query.count()
    
    # 获取分页数据，并按创建时间倒序排序
    favorites = favorites_query.order_by(Favorite.created_at.desc()).offset(skip).limit(page_size).all()
    
    # 获取关联的文章详情
    articles = [favorite.article for favorite in favorites if favorite.article.status == "published"]
    
    return {
        "data": {
            "items": articles,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }
