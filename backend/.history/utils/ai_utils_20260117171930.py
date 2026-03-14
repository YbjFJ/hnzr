from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from config import settings

# ================= 全局 AI 实例缓存 =================

_global_llm = None
_global_embeddings = None


def get_llm():
    """获取全局唯一的 LLM 实例 (懒加载)"""
    global _global_llm
    if _global_llm is None:
    print("⚡ [系统]: 初始化 LLM 单例对象...")
     _global_llm = ChatOpenAI(
        model='doubao-1-5-pro-32k-250115',
        openai_api_key=settings.doubao_api_key,
        openai_api_base='https://ark.cn-beijing.volces.com/api/v3',
        streaming=True,
        temperature=0.3
    )
    return _global_llm


def get_embeddings():
    """获取全局唯一的 Embeddings 实例 (懒加载)"""
    global _global_embeddings
    if _global_embeddings is None:
        print("⚡ [系统]: 初始化 Embeddings 单例对象...")
        _global_embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            openai_api_key=settings.deepseek_api_key,
            openai_api_base='https://api.deepseek.com'
        )
    return _global_embeddings
