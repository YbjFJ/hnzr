import asyncio
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


def generate_article_from_search(query):
    """
    根据搜索结果生成新闻咨询
    """
    # 1. 进行网络搜索
    search_results = web_search(query, max_results=3)
    
    # 2. 提取搜索结果
    search_content = ""
    for result in search_results.get("results", []):
        search_content += f"标题: {result.get('title', '')}\n"
        search_content += f"链接: {result.get('url', '')}\n"
        search_content += f"摘要: {result.get('content', '')}\n\n"
    
    # 3. 构建AI提示词
    prompt = f"""根据以下搜索结果，生成一篇高质量的新闻咨询文章：

{search_content}

要求：
1. 标题要吸引人，突出核心内容
2. 内容结构清晰，包括引言、主体和结论
3. 语言流畅，信息准确
4. 字数控制在500-1000字
5. 格式为Markdown
6. 确保文章内容与搜索结果相关，并且是原创的
7. 不要提及搜索结果或AI生成
8. 加入适当的小标题和段落分隔

新闻标题：
"""
    
    # 4. 调用AI生成文章
    llm = get_llm()
    try:
        ai_response = llm.invoke(prompt)
        article_content = ai_response.content
        
        # 提取标题和正文
        lines = article_content.split('\n')
        title = lines[0] if lines else ""
        content = '\n'.join(lines[1:]) if len(lines) > 1 else ""
        
        return {
            "title": title.strip(),
            "content": content.strip(),
            "summary": content[:200] + "..." if len(content) > 200 else content
        }
    except Exception as e:
        print(f"文章生成失败: {e}")
        return None
