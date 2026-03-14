import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "mysql+pymysql://root:1234@localhost:3306/news_platform?charset=utf8mb4"  # MySQL配置
    
    # API配置
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AI咨询网络平台"
    
    # CORS配置
    CORS_ORIGINS: list[str] = ["*"]
    
    # JWT配置
    SECRET_KEY: str = "your-secret-key"  # 生产环境请使用随机生成的密钥
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
