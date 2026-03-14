import asyncio
from fastapi import logger
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
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
    根据搜索结果生成新闻咨询（增强版）
    """
    # 1. 获取当前日期，确保新闻时效性准确
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # 2. 异步执行搜索
    logger.info(f"正在搜索关键词: {query}")
    search_response = await web_search(query, max_results=5, search_depth="advanced")
    results = search_response.get("results", [])
    
    if not results:
        logger.warning("未找到相关搜索结果")
        return None

    # 3. 构建上下文（带引用索引）
    context_text = ""
    for idx, res in enumerate(results, 1):
        context_text += f"[{idx}] 来源: {res.get('title')} ({res.get('url')})\n"
        context_text += f"    摘要: {res.get('content')}\n\n"

    # 4. 构建高级 Prompt
    system_prompt = f"""你是一名拥有10年经验的资深新闻主编。今天是 {today_date}。
你的任务是根据提供的互联网搜索结果，写一篇深度、客观、引人入胜的新闻综述文章。

要求：
1. **真实性**：严格基于搜索结果，不要编造事实。文中的关键事实请标注来源索引，如 [1], [2]。
2. **结构**：包含引人入胜的标题、简短的摘要（导语）、正文（分小标题）、结论。
3. **格式**：正文使用 Markdown 格式。
4. **语气**：专业、客观、流畅，适合行业读者阅读。

请严格返回合法的 JSON 格式数据，不要包含 Markdown 的代码块标记（如 ```json），格式如下：
{{
    "title": "文章标题",
    "summary": "200字以内的文章摘要",
    "content": "完整的Markdown格式正文内容"
}}
"""

    user_prompt = f"""搜索关键词："{query}"

搜索结果数据：
{context_text}

请开始生成文章："""

    # 5. 调用 AI (使用异步 invoke)
    llm = get_llm() # 确保你的 LLM 配置支持较大的上下文
    
    try:
        # 使用 LangChain 的消息结构
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 假设 llm 支持 ainvoke (LangChain 标准异步方法)
        # 如果你的 llm 实例不支持 ainvoke，请使用 await loop.run_in_executor(None, llm.invoke, messages)
        ai_response = await llm.ainvoke(messages)
        response_text = ai_response.content.strip()

        # 清理可能存在的 Markdown 代码块标记
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        # 解析 JSON
        article_data = json.loads(response_text)
        
        # 简单的数据清洗
        return {
            "title": article_data.get("title", "无标题"),
            "content": article_data.get("content", ""),
            "summary": article_data.get("summary", "")
        }

    except json.JSONDecodeError:
        logger.error(f"JSON 解析失败，AI 返回原始内容: {response_text}")
        # 降级处理：如果不幸返回了纯文本，尝试手动提取（略）或直接返回错误
        return None
    except Exception as e:
        logger.error(f"文章生成出错: {str(e)}")
        return None