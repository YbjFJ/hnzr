from pathlib import Path
from pydantic import Field  # <--- 1. 记得导入 Field
from pydantic_settings import BaseSettings

# 固定从 config.py 所在目录加载 .env，避免因启动目录不同而读不到配置
_ENV_FILE = Path(__file__).resolve().parent / ".env"

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = Field(default="", alias="DATABASE_URL")
    
    # API配置
    API_V1_STR: str = Field(default="/api/v1", alias="API_V1_STR")
    PROJECT_NAME: str = Field(default="AI咨询网络平台", alias="PROJECT_NAME")
    
    # CORS配置
    CORS_ORIGINS: list[str] = Field(default=["*"], alias="CORS_ORIGINS")
    
    # JWT配置
    SECRET_KEY: str = Field(default="", alias="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", alias="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_DAYS: int = Field(default=3, alias="ACCESS_TOKEN_EXPIRE_DAYS")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=4320, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    
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
    TAVILY_API_KEY: str = Field(default="", alias="TAVILY_API_KEY")

    BOCHA_API_KEY: str = Field(default="", alias="BOCHA_API_KEY")

    JINA_API_KEY: str = Field(default="", alias="JINA_API_KEY")

    # 邮件配置（QQ 邮箱等，忘记密码验证码；不配置则仅控制台打印验证码）
    MAIL_SERVER: str = Field(default="", alias="MAIL_SERVER")
    MAIL_PORT: int = Field(default=465, alias="MAIL_PORT")
    MAIL_USERNAME: str = Field(default="", alias="MAIL_USERNAME")
    MAIL_PASSWORD: str = Field(default="", alias="MAIL_PASSWORD")
    MAIL_USE_SSL: bool = Field(default=True, alias="MAIL_USE_SSL")

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "allow"
        
        # 注意：当你使用了 Field(alias=...) 后，下面的 alias_generator 对这些特定字段就不生效了
        # 但对其他未指定 alias 的字段依然有效
        # alias_generator = lambda field_name: field_name.upper() 

settings = Settings()