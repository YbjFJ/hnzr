import asyncio
from asyncio.log import logger
import datetime
import json
import re
from typing import Dict
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser # 新增：专用的JSON解析器
from config import settings
from tavily import TavilyClient

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
            model='ep-20250517101556-hq2sg',
            openai_api_key=settings.doubao_api_key,
            openai_api_base='https://ark.cn-beijing.volces.com/api/v3',
            check_embedding_ctx_length=False
        )
        
    return _global_embeddings


def build_vectorstore_from_articles(articles):
    """
    从文章列表构建向量数据库
    """
    # 将文章转换为 Document 对象
    docs = []
    for article in articles:
        # 构建文章内容，包含标题、摘要和正文
        content = f"标题: {article.title}\n"
        if article.summary:
            content += f"摘要: {article.summary}\n"
        content += f"内容: {article.content}"
        
        # 确保内容是字符串类型
        content = str(content) if content else ""
        
        # 添加元数据
        metadata = {
            "article_id": article.id,
            "title": article.title,
            "publish_date": article.publish_date,
            "type": article.type,
            "source_name": article.source_name
        }
        
        doc = Document(page_content=content, metadata=metadata)
        docs.append(doc)
    
    # 分割文档，优化检索效果
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=60,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", "\s"]
    )
    splits = text_splitter.split_documents(docs)
    
    # 确保分割后的内容都是字符串
    for i, split in enumerate(splits):
        if not isinstance(split.page_content, str):
            splits[i].page_content = str(split.page_content) if split.page_content else ""
    
    # 提取文本列表和元数据列表
    texts = [split.page_content for split in splits]
    metadatas = [split.metadata for split in splits]
    
    # 过滤掉空文本
    texts_with_metadata = [(text, meta) for text, meta in zip(texts, metadatas) if text.strip()]
    if not texts_with_metadata:
        return None
    
    filtered_texts, filtered_metadatas = zip(*texts_with_metadata)
    
    # 构建向量数据库
    embeddings = get_embeddings()
    vectorstore = FAISS.from_texts(
        texts=list(filtered_texts),
        embedding=embeddings,
        metadatas=list(filtered_metadatas)
    )
    
    return vectorstore


def retrieve_relevant_content(query, articles, k=3):
    """
    从文章列表中检索与查询相关的内容
    """
    if not articles:
        return []
    
    # 构建向量数据库
    vectorstore = build_vectorstore_from_articles(articles)
    
    # 处理向量数据库构建失败的情况
    if not vectorstore:
        return []
    
    # 相似度搜索，获取最相关的内容
    retrieved_docs = vectorstore.similarity_search(query, k=k)
    
    return retrieved_docs



async def web_search(query: str, max_results: int = 5, search_depth: str = "advanced") -> Dict:
    """
    异步执行 Tavily 网络搜索，增强时效性和深度
    """
    tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
    
    try:
        # 在 executor 中运行同步的搜索代码，避免阻塞 FastAPI 主线程
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: tavily.search(
                query=query,
                search_depth=search_depth, # basic 或 advanced
                max_results=max_results,
                include_answer=True,
                include_raw_content=False,
                # 可以限制搜索最近几天的新闻，例如 "d" (天), "w" (周), "m" (月)
                # time_range="w" 
            )
        )
        return response
    except Exception as e:
        logger.error(f"Tavily 搜索失败: {str(e)}")
        return {"results": []}


async def generate_article_from_search(query: str):
    """
    根据搜索结果生成新闻咨询（修复JSON解析版）
    """
    # 1. 获取当前日期
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # 2. 异步执行搜索
    logger.info(f"正在搜索关键词: {query}")
    search_response = await web_search(query, max_results=5, search_depth="advanced")
    results = search_response.get("results", [])

    # 提取非空的 URL 组成一个列表
    source_urls_list = [res.get('url') for res in results if res.get('url')]
    
    if not results:
        logger.warning("未找到相关搜索结果")
        return None

    # 3. 构建上下文
    context_text = ""
    for idx, res in enumerate(results, 1):
        context_text += f"[{idx}] 来源: {res.get('title')} ({res.get('url')})\n"
        context_text += f"    摘要: {res.get('content')}\n\n"

    # 4. 初始化 LangChain 的 JSON 解析器
    parser = JsonOutputParser()
    format_instructions = parser.get_format_instructions()

    # 5. 构建 Prompt (增加了格式指令和换行符警告)
    system_prompt = f"""你是一名资深新闻主编。今天是 {today_date}。
请根据搜索结果撰写一篇深度新闻综述。

重要格式要求：
1. 必须返回合法的 JSON 格式。
2. **JSON 字符串内的换行符必须使用转义字符 '\\n'，严禁直接换行。**
3. 包含 keys: "title", "summary", "content"。
4. 正文 (content) 使用 Markdown 格式。

{format_instructions}
"""

    user_prompt = f"""搜索关键词："{query}"

搜索结果数据：
{context_text}

请生成文章（JSON格式）："""

    # 6. 调用 AI
    llm = get_llm()
    
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        ai_response = await llm.ainvoke(messages)
        response_text = ai_response.content.strip()

        # --- 解析阶段 (三层保险) ---

        # 第一层：尝试使用 LangChain 专用解析器 (能自动处理 ```json 等标记)
        try:
            article_data = parser.parse(response_text)
            return validate_and_fix_data(article_data)
        except Exception:
            logger.warning("LangChain Parser 解析失败，尝试手动清洗...")

        # 第二层：手动清洗 + json.loads
        # 去除 markdown 标记
        clean_text = re.sub(r'^```json\s*', '', response_text, flags=re.MULTILINE)
        clean_text = re.sub(r'^```\s*', '', clean_text, flags=re.MULTILINE)
        clean_text = clean_text.strip().rstrip('`')
        
        # 尝试修复未转义的换行符 (这是一个常见的 LLM JSON 错误)
        # 这是一个简单的启发式修复：如果一行不以 " 结尾且下一行不以 " 开头，可能是断行了
        # 但最安全的是使用 re.DOTALL 提取
        try:
            article_data = json.loads(clean_text)
            return validate_and_fix_data(article_data)
        except json.JSONDecodeError:
            logger.warning("标准 JSON 解析失败，进入正则强制提取模式...")

        # 第三层：正则强制提取 (最后的兜底)
        # 即使 JSON 格式烂掉了，只要有 title 和 content 的文本在，我们就能提取
        title_match = re.search(r'"title"\s*:\s*"(.*?)"', response_text)
        # 摘要提取
        summary_match = re.search(r'"summary"\s*:\s*"(.*?)"', response_text)
        # 内容提取 (最难，因为它包含换行，使用 DOTALL 模式)
        # 匹配 "content": " 到 结尾的 " (注意处理转义引号)
        content_match = re.search(r'"content"\s*:\s*"(.*)"\s*\}', response_text, re.DOTALL)
        
        if not content_match:
             # 尝试另一种匹配，匹配到倒数第二个引号
             content_match = re.search(r'"content"\s*:\s*"(.*)', response_text, re.DOTALL)

        if title_match and content_match:
            title = title_match.group(1)
            content = content_match.group(1).rstrip('"').rstrip().rstrip('}')
            summary = summary_match.group(1) if summary_match else content[:100]
            
            # 简单的转义修复
            content = content.replace('\\n', '\n').replace('\\"', '"')
            
            return {
                "title": title,
                "summary": summary,
                "content": content,
                "source_urls": source_urls_list  # <--- 把 URL 列表传出去
            }
            
        raise Exception("无法从 AI 响应中提取有效数据")

    except Exception as e:
        logger.error(f"文章生成全流程失败: {str(e)}")
        logger.error(f"原始响应片段: {response_text[:500]}...") # 打印一部分以便调试
        return None

def validate_and_fix_data(data):
    """辅助函数：确保数据结构完整"""
    if not isinstance(data, dict):
        return None
    return {
        "title": data.get("title", "未命名文章"),
        "summary": data.get("summary", "暂无摘要"),
        "content": data.get("content", "")
    }