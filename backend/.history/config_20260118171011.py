import os
from pydantic import Field  # <--- 1. 记得导入 Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "mysql+pymysql://root:1234@localhost:3306/news_platform?charset=utf8mb4"
    
    # API配置
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AI咨询网络平台"
    
    # CORS配置
    CORS_ORIGINS: list[str] = ["*"]
    
    # JWT配置
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 3
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 3 * 24 * 60
    
    # AI模型配置 (修改了这里)
    # alias="环境变量名"：告诉Pydantic去环境变量里找这个名字
    # default=""：如果没找到，就默认为空字符串（防止报错）
    
    # 1. DeepSeek
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    
    # 2. 豆包 (对应你截图里的 ARK_API_KEY)
    doubao_api_key: str = Field(default="", alias="ARK_API_KEY")
    
    # 3. 通义千问 (对应你截图里的 DASHSCOPE_API_KEY)
    qwen_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    
    # 4. Tavily 搜索 API
    TAVILY_API_KEY: str = Field(default="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", alias="TAVILY_API_KEY")

    BOCHA_API_KEY: str = Field(default="sk-3585c34752d64f5eb1524569be9debfe",alias="BOCHA_API_KEY")

    

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "allow"
        
        # 注意：当你使用了 Field(alias=...) 后，下面的 alias_generator 对这些特定字段就不生效了
        # 但对其他未指定 alias 的字段依然有效
        # alias_generator = lambda field_name: field_name.upper() 

settings = Settings()