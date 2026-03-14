from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import sqlalchemy
from sqlalchemy import create_engine

from config import settings
from database import engine
from models import Base
from controller.user import router as user_router
from controller.category import router as category_router
from controller.report import router as report_router
from controller.article import router as article_router
from controller.chat import router as chat_router

# 自动创建数据库
# 1. 先解析出数据库连接信息，创建不带数据库名的引擎
import re

db_url = settings.DATABASE_URL
# 提取数据库名
match = re.search(r'/([^/]+)\?', db_url)
if match:
    db_name = match.group(1)
    # 创建不带数据库名的连接URL
    base_db_url = db_url.replace(f"/{db_name}?", "?")
    
    try:
        # 连接到MySQL服务器
        base_engine = create_engine(base_db_url)
        with base_engine.connect() as conn:
            # 创建数据库（如果不存在）
            conn.execute(sqlalchemy.text(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            print(f"Database '{db_name}' checked/created successfully!")
    except Exception as e:
        print(f"Error checking/creating database: {e}")

# 创建数据库表
Base.metadata.create_all(bind=engine)
print("Database tables created successfully!")

# 创建FastAPI应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置全局缓存依赖项，在请求结束时清空缓存
from utils.global_cache import global_cache_dependency
app.router.dependencies.append(Depends(global_cache_dependency))

# 注册路由
app.include_router(user_router, prefix=settings.API_V1_STR)
app.include_router(category_router, prefix=settings.API_V1_STR)
app.include_router(article_router, prefix=settings.API_V1_STR)
app.include_router(report_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)

# 根路径
@app.get("/")
def read_root():
    return {"message": "Welcome to AI咨询网络平台 API", "version": "1.0.0"}

# 健康检查
@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8002)
