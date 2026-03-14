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
import httpx
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


async def web_search_bocha(query: str, max_results: int = 5, days: int = 7) -> Dict:
    """
    使用 Bocha (博查) 搜索引擎，专注于中文政策和新闻
    """
    # 你的博查 API Key (建议放入 settings 或环境变量)
    BOCHA_API_KEY = settings.BOCHA_API_KEY 
    API_URL = "https://api.bochaai.com/v1/web-search"

    # === 搜索词优化策略 ===
    # 为了尊重原文，我们给用户的关键词自动加上后缀
    # 这样能极大提高搜到政府官网(.gov.cn)的概率
    optimized_query = f"{query} 政策原文 site:gov.cn" 
    # 或者用更宽泛的: optimized_query = f"{query} 政策发布"

    headers = {
        "Authorization": f"Bearer {BOCHA_API_KEY}",
        "Content-Type": "application/json"
    }

    # Bocha 的时间参数通常是 'oneDay', 'oneWeek', 'oneMonth', 'oneYear', 'noLimit'
    freshness = "noLimit"
    if days <= 1: freshness = "oneDay"
    elif days <= 7: freshness = "oneWeek"
    elif days <= 30: freshness = "oneMonth"
    elif days <= 365: freshness = "oneYear"

    payload = {
        "query": optimized_query,
        "freshness": freshness, 
        "summary": True,      # 让博查生成摘要
        "count": max_results
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(API_URL, headers=headers, json=payload, timeout=30.0)
            
            if resp.status_code != 200:
                logger.error(f"Bocha 搜索 API 错误: {resp.text}")
                return {"results": []}

            data = resp.json()
            
            # 格式化为与你之前代码兼容的格式
            # Bocha 返回结构通常在 data['data']['webPages']['value'] 中
            formatted_results = []
            
            # 注意：Bocha 的返回结构可能会更新，请参考最新文档
            # 假设结构为 data['data'] 是列表
            raw_results = data.get("data", {}).get("webPages", {}).get("value", [])
            
            for item in raw_results:
                formatted_results.append({
                    "title": item.get("name") or item.get("title"),
                    "url": item.get("url"),
                    "content": item.get("snippet") or item.get("summary", ""),
                    "published_date": item.get("dateLastCrawled") or "近期" # Bocha 可能不直接返回 publish_date，用抓取时间代替
                })

            return {"results": formatted_results}

    except Exception as e:
        logger.error(f"Bocha 搜索异常: {str(e)}")
        return {"results": []}
    

async def web_search_travily(query: str, max_results: int = 5, days: int = 7) -> Dict:
    """
    异步执行 Tavily 网络搜索，专注于近期新闻
    :param days: 搜索过去多少天的数据 (默认3天)
    """
    tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
    
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: tavily.search(
                query=query,
                search_depth="advanced",
                topic="news",           # <--- 关键：指定搜索新闻主题
                days=days,              # <--- 关键：限制过去 N 天
                max_results=max_results,
                include_answer=True,
                include_raw_content=False,
                include_images=False
            )
        )
        return response
    except Exception as e:
        logger.error(f"Tavily 搜索失败: {str(e)}")
        return {"results": []}

# 1. 新增：抓取网页正文的辅助函数
async def fetch_url_content(url: str) -> str:
    """
    使用 Jina Reader 将网页转换为对 LLM 友好的 Markdown
    """
    jina_url = f"https://r.jina.ai/{url}"
    
    # 可以在 header 中加 Authorization 使用免费 API Key 提高额度，
    # 不加 key 也有免费额度，通常够用
    headers = {
        "Authorization": "Bearer "+settings.JINA_API_KEY, 
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(jina_url, headers=headers)
            if resp.status_code == 200:
                # 截取前 8000 字符，防止 token 爆炸
                return resp.text[:8000]
            else:
                return ""
    except Exception as e:
        logger.warning(f"抓取网页失败 {url}: {e}")
        return ""
    

# 2. 修改：主生成逻辑
async def generate_article_from_search(query: str):
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # --- 第一步：搜索 ---
    logger.info(f"正在搜索关键词: {query}")
    # 建议加上 "政策原文" 或 "全文" 关键词
    search_query = f"{query} 政策原文" 
    search_response = await web_search_bocha(search_query, max_results=5, days=30) 
    results = search_response.get("results", [])

    source_urls_list = [res.get('url') for res in results if res.get('url')]
    
    if not results:
        return None

    # --- 第二步：核心修改 - 抓取前 2 个结果的全文 ---
    # 搜索结果的 snippet 往往是垃圾，必须进网页看
    logger.info("正在抓取网页正文...")
    
    # 我们只抓取前 2 个，因为全抓太慢且 Token 会超
    top_results = results[:2]
    
    # 并发抓取
    tasks = [fetch_url_content(res['url']) for res in top_results]
    contents = await asyncio.gather(*tasks)
    
    # --- 第三步：构建更丰富的上下文 ---
    context_text = ""
    for idx, (res, full_content) in enumerate(zip(top_results, contents), 1):
        # 如果抓到了正文，就用正文；没抓到就用原来的摘要
        display_content = full_content if len(full_content) > 200 else res.get('content', '')
        
        context_text += f"=== 文档 [{idx}] ===\n"
        context_text += f"标题: {res.get('title')}\n"
        context_text += f"链接: {res.get('url')}\n"
        context_text += f"内容:\n{display_content}\n\n"
        
    # 如果抓取失败，把剩下的结果作为补充
    for idx, res in enumerate(results[2:], 3):
         context_text += f"=== 文档 [{idx}] (仅摘要) ===\n"
         context_text += f"标题: {res.get('title')}\n"
         context_text += f"摘要: {res.get('content')}\n\n"

    # --- 第四步：Prompt 微调 (允许摘要) ---
    # 既然我们尽力抓取了，如果还是没有，允许 AI 做简报，而不是直接罢工
    parser = JsonOutputParser()
    format_instructions = parser.get_format_instructions()

    system_prompt = f"""你是一名政府政策档案整理员。今天是 {today_date}。

        任务：根据提供的【文档内容】整理关于“{query}”的政策档案。

        **处理原则：**
        1. **优先还原原文**：如果【文档内容】中包含“第一条、第二条”等具体条款，请精确还原。
        2. **允许摘要**：如果【文档内容】仅为新闻报道或通知，提取其中的核心政策点（如金额、时间、对象）。
        3. **如实告知**：如果内容完全不相关，返回 JSON 中的 content 字段填写 "未找到有效政策内容"。

        **输出要求：**
        1. 标题：使用文档中的官方标题。
        2. 正文：Markdown 格式，结构化展示。
        3. 必须返回 JSON。

        {format_instructions}
        """

    user_prompt = f"""参考文档数据：
        {context_text}

        请生成 JSON："""

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

        # 第一层：LangChain 专用解析器
        try:
            article_data = parser.parse(response_text)
            # === 修复：传入 source_urls_list ===
            return validate_and_fix_data(article_data, source_urls_list)
        except Exception:
            logger.warning("LangChain Parser 解析失败，尝试手动清洗...")

        # 第二层：手动清洗 + json.loads
        clean_text = re.sub(r'^```json\s*', '', response_text, flags=re.MULTILINE)
        clean_text = re.sub(r'^```\s*', '', clean_text, flags=re.MULTILINE)
        clean_text = clean_text.strip().rstrip('`')
        
        try:
            article_data = json.loads(clean_text)
            # === 修复：传入 source_urls_list ===
            return validate_and_fix_data(article_data, source_urls_list)
        except json.JSONDecodeError:
            logger.warning("标准 JSON 解析失败，进入正则强制提取模式...")

        # 第三层：正则强制提取 (兜底)
        title_match = re.search(r'"title"\s*:\s*"(.*?)"', response_text)
        summary_match = re.search(r'"summary"\s*:\s*"(.*?)"', response_text)
        content_match = re.search(r'"content"\s*:\s*"(.*)"\s*\}', response_text, re.DOTALL)
        
        if not content_match:
             content_match = re.search(r'"content"\s*:\s*"(.*)', response_text, re.DOTALL)

        if title_match and content_match:
            title = title_match.group(1)
            content = content_match.group(1).rstrip('"').rstrip().rstrip('}')
            summary = summary_match.group(1) if summary_match else content[:100]
            
            content = content.replace('\\n', '\n').replace('\\"', '"')
            
            return {
                "title": title,
                "summary": summary,
                "content": content,
                "source_urls": source_urls_list  # 这里你之前已经写对了
            }
            
        raise Exception("无法从 AI 响应中提取有效数据")

    except Exception as e:
        logger.error(f"文章生成全流程失败: {str(e)}")
        # 调试时很有用
        return None

# === 修改后的辅助函数 ===
def validate_and_fix_data(data, source_urls):
    """
    辅助函数：确保数据结构完整，并注入 URL 列表
    """
    if not isinstance(data, dict):
        return None
    
    return {
        "title": data.get("title", "未命名文章"),
        "summary": data.get("summary", "暂无摘要"),
        "content": data.get("content", ""),
        # 这里强制使用我们要保存的真实 URL 列表
        "source_urls": source_urls 
    }