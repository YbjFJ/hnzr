import contextvars

# 创建上下文变量用于存储全局缓存
_global_cache = contextvars.ContextVar("global_cache", default={})

def get_global_cache():
    """
    获取全局缓存字典
    """
    return _global_cache.get()

def set_global_cache(key, value):
    """
    设置全局缓存值
    """
    cache = get_global_cache()
    cache[key] = value
    _global_cache.set(cache)

def get_global_cache_value(key, default=None):
    """
    获取全局缓存中的特定值
    """
    cache = get_global_cache()
    return cache.get(key, default)

def clear_global_cache():
    """
    清空全局缓存
    """
    _global_cache.set({})

# 创建FastAPI依赖项，用于在请求结束时清空缓存
from fastapi import Depends
from starlette.requests import Request

async def global_cache_dependency(request: Request):
    """
    FastAPI依赖项，用于在请求结束时清空全局缓存
    """
    yield
    # 请求处理完成后清空缓存
    clear_global_cache()
