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


import httpx
from typing import Dict
# import settings # 你的配置模块

async def web_search_bocha(query: str, max_results: int = 5, days: int = 7) -> Dict:
    """
    使用 Bocha (博查) 搜索引擎，专注于国务院及国家级中央政策
    """
    # 你的博查 API Key
    BOCHA_API_KEY = settings.BOCHA_API_KEY 
    API_URL = "https://api.bochaai.com/v1/web-search"

    # === 核心优化策略 ===
    # 1. 限定域名：
    #    - www.gov.cn: 中国政府网 (国务院及其办公厅发布平台)
    #    - *.ndrc.gov.cn: 国家发改委
    #    - *.miit.gov.cn: 工信部
    #    - *.mof.gov.cn: 财政部
    #    (根据需要可以加更多，但过长可能导致搜索截断，建议主要锁定 gov.cn + 关键词)
    
    # 2. 关键词加权：
    #    强制包含 "国务院" 或 "中央" 或 "办公厅" 等词汇
    
    # 方法 A (精准打击): 只搜中国政府网 (最推荐，最权威)
    # optimized_query = f"{query} site:www.gov.cn"
    
    # 方法 B (广度兼顾权威): 搜 gov.cn 但强制要求是中央级别的词
    # 语法解释：(A | B) 表示 A 或 B，site:gov.cn 限制政府域名
    keywords_weight = "(国务院 | 中央 | 国家发改委 | 办公厅 | 政策库)"
    optimized_query = f"{query} {keywords_weight} site:gov.cn"

    # 调试打印，方便你看最终发给博查的是什么
    logger.info(f"Bocha Search Query: {optimized_query}")

    headers = {
        "Authorization": f"Bearer {BOCHA_API_KEY}",
        "Content-Type": "application/json"
    }

    # 时间参数映射
    freshness = "noLimit"
    if days <= 1: freshness = "oneDay"
    elif days <= 7: freshness = "oneWeek"
    elif days <= 30: freshness = "oneMonth"
    elif days <= 365: freshness = "oneYear"

    payload = {
        "query": optimized_query,
        "freshness": freshness, 
        "summary": True,
        "count": max_results
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(API_URL, headers=headers, json=payload, timeout=30.0)
            
            if resp.status_code != 200:
                logger.error(f"Bocha 搜索 API 错误: {resp.text}")
                return {"results": []}

            data = resp.json()
            
            formatted_results = []
            # 获取 webPages 列表
            raw_results = data.get("data", {}).get("webPages", {}).get("value", [])
            
            for item in raw_results:
                title = item.get("name") or item.get("title")
                snippet = item.get("snippet") or item.get("summary", "")
                url = item.get("url", "")
                
                # === 二次过滤 (可选) ===
                # 如果你想确保万无一失，可以在这里再过滤一遍
                # 比如只保留 www.gov.cn 的结果
                # if "www.gov.cn" not in url: continue 

                formatted_results.append({
                    "title": title,
                    "url": url,
                    "content": snippet,
                    "published_date": item.get("dateLastCrawled") or "近期"
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
    
from langchain_core.pydantic_v1 import BaseModel, Field

# 定义期望的数据结构
class ArticleSchema(BaseModel):
    title: str = Field(description="文章的标题，必须是字符串")
    summary: str = Field(description="文章的摘要，200字以内")
    content: str = Field(description="文章的正文，Markdown格式，必须是单个长字符串，不要使用列表")


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
    parser = JsonOutputParser(pydantic_object=ArticleSchema)
    format_instructions = parser.get_format_instructions()

    system_prompt = f"""你是一名资深的政策研究员及党政新闻编辑。今天是 {today_date}。
        任务：基于提供的多篇【参考文档】，撰写一篇关于“{query}”的**深度政策综述**。

        **核心指令（格式与渲染）：**
        1. **强制换行（关键）：** Markdown 标题（如 `## 标题`）的前面**必须**包含两个换行符 (`\\n\\n`)。严禁将正文与下一个标题连在同一行，否则会导致页面渲染失败。
        2. **JSON格式：** 返回单纯的 JSON 对象，Key 为 `title`, `summary`, `content`。`content` 是单字符串。

        **核心原则：**
        1. **政治站位与客观性**：保持公文及政治新闻的严肃性、权威性。用词需精准、客观（如使用“指出”、“强调”、“明确”、“印发”），严禁使用营销号、口语化或情绪化用语。
        2. **忠实原文与内容丰富**：
           - **数据铁律**：文中涉及的补贴标准、时间节点、文号、指标数据必须与【参考文档】完全一致，**严禁篡改或臆造**。
           - **内容充实**：不要只写摘要。如果文档中有具体的实施细则（如申报流程、限制条件），请详细列出，确保文章具有实用参考价值。
        3. **逻辑重组（关键）**：
           - **不要**简单地按“文档1、文档2”罗列。
           - **要**根据内容逻辑进行整合。例如分为“政策背景”、“核心举措”、“资金支持”、“工作要求”等板块。将不同文档中关于同一主题的内容合并叙述。

        **输出格式严格要求（JSON）：**
        1. **必须**返回一个单纯的 JSON 对象，**严禁**包含 markdown 代码块标记（如 ```json）。
        2. JSON 的 Key 必须是英文：`title`, `summary`, `content`。
        3. `content` 字段必须是**一个**长字符串（使用 \\n 换行），**不能**是数组或列表。

        **文章结构要求（content字段）：**
        1. **导语**：简要概述近期关于“{query}”的政策动态或总体形势。
        2. **正文**：使用 Markdown 的 `##` 二级标题进行分块阐述。
           - 建议结构：【总体目标/背景】 -> 【核心政策/具体措施】 -> 【保障机制/资金安排】 -> 【下一步工作部署】。
           - 对于关键条款，可以使用无序列表 `-` 清晰展示。
        3. **结语**：简要总结或注明政策有效期（如有）。

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

        # 清理一下 markdown 标记，防止 parse 报错
        clean_text = response_text.replace("```json", "").replace("```", "").strip()

        try:
            # 尝试直接解析 JSON
            article_data = json.loads(clean_text)
            return validate_and_fix_data(article_data, source_urls_list)
        except json.JSONDecodeError:
            # 如果 JSON 格式坏了，尝试用 LangChain 的 parser 修复
            try:
                article_data = parser.parse(clean_text)
                return validate_and_fix_data(article_data, source_urls_list)
            except Exception as e:
                logger.error(f"解析彻底失败: {e}\n原文: {clean_text}")
                return None

    except Exception as e:
        logger.error(f"文章生成全流程失败: {str(e)}")
        # 调试时很有用
        return None


async def generate_article_from_search_stream(query: str):
    """
    流式版：逐步 yield 进度文案，最后 yield 含 [ARTICLE_JSON] 的一行供 controller 落库。
    """
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # --- 第一步：搜索 ---
    logger.info(f"正在搜索关键词: {query}")
    search_query = f"{query} 政策原文"
    search_response = await web_search_bocha(search_query, max_results=5, days=30)
    results = search_response.get("results", [])
    source_urls_list = [res.get("url") for res in results if res.get("url")]

    if not results:
        yield "[ERROR] 未找到相关政策新闻出处\n"
        return

    yield "已经找到相关政策新闻出处\n"

    # --- 第二步：抓取正文 ---
    logger.info("正在抓取网页正文...")
    top_results = results[:2]
    tasks = [fetch_url_content(res["url"]) for res in top_results]
    contents = await asyncio.gather(*tasks)

    yield "已经搜索提取到相关内容\n"

    # --- 第三步：构建上下文 ---
    context_text = ""
    for idx, (res, full_content) in enumerate(zip(top_results, contents), 1):
        display_content = full_content if len(full_content) > 200 else res.get("content", "")
        context_text += f"=== 文档 [{idx}] ===\n"
        context_text += f"标题: {res.get('title')}\n"
        context_text += f"链接: {res.get('url')}\n"
        context_text += f"内容:\n{display_content}\n\n"
    for idx, res in enumerate(results[2:], 3):
        context_text += f"=== 文档 [{idx}] (仅摘要) ===\n"
        context_text += f"标题: {res.get('title')}\n"
        context_text += f"摘要: {res.get('content')}\n\n"

    yield "AI开始生成\n"

    parser = JsonOutputParser(pydantic_object=ArticleSchema)
    format_instructions = parser.get_format_instructions()
    system_prompt = f"""你是一名资深的政策研究员及党政新闻编辑。今天是 {today_date}。
        任务：基于提供的多篇【参考文档】，撰写一篇关于“{query}”的**深度政策综述**。

        **核心指令（格式与渲染）：**
        1. **强制换行（关键）：** Markdown 标题（如 `## 标题`）的前面**必须**包含两个换行符 (`\\n\\n`)。严禁将正文与下一个标题连在同一行，否则会导致页面渲染失败。
        2. **JSON格式：** 返回单纯的 JSON 对象，Key 为 `title`, `summary`, `content`。`content` 是单字符串。

        **核心原则：**
        1. **政治站位与客观性**：保持公文及政治新闻的严肃性、权威性。用词需精准、客观（如使用“指出”、“强调”、“明确”、“印发”），严禁使用营销号、口语化或情绪化用语。
        2. **忠实原文与内容丰富**：
           - **数据铁律**：文中涉及的补贴标准、时间节点、文号、指标数据必须与【参考文档】完全一致，**严禁篡改或臆造**。
           - **内容充实**：不要只写摘要。如果文档中有具体的实施细则（如申报流程、限制条件），请详细列出，确保文章具有实用参考价值。
        3. **逻辑重组（关键）**：
           - **不要**简单地按“文档1、文档2”罗列。
           - **要**根据内容逻辑进行整合。例如分为“政策背景”、“核心举措”、“资金支持”、“工作要求”等板块。将不同文档中关于同一主题的内容合并叙述。

        **输出格式严格要求（JSON）：**
        1. **必须**返回一个单纯的 JSON 对象，**严禁**包含 markdown 代码块标记（如 ```json）。
        2. JSON 的 Key 必须是英文：`title`, `summary`, `content`。
        3. `content` 字段必须是**一个**长字符串（使用 \\n 换行），**不能**是数组或列表。

        **文章结构要求（content字段）：**
        1. **导语**：简要概述近期关于“{query}”的政策动态或总体形势。
        2. **正文**：使用 Markdown 的 `##` 二级标题进行分块阐述。
           - 建议结构：【总体目标/背景】 -> 【核心政策/具体措施】 -> 【保障机制/资金安排】 -> 【下一步工作部署】。
           - 对于关键条款，可以使用无序列表 `-` 清晰展示。
        3. **结语**：简要总结或注明政策有效期（如有）。

        {format_instructions}
    """
    user_prompt = f"""参考文档数据：
        {context_text}

        请生成 JSON："""

    llm = get_llm()
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        ai_response = await llm.ainvoke(messages)
        response_text = ai_response.content.strip()
        clean_text = response_text.replace("```json", "").replace("```", "").strip()

        try:
            article_data = json.loads(clean_text)
            data = validate_and_fix_data(article_data, source_urls_list)
        except json.JSONDecodeError:
            try:
                article_data = parser.parse(clean_text)
                data = validate_and_fix_data(article_data, source_urls_list)
            except Exception as e:
                logger.error(f"解析彻底失败: {e}\n原文: {clean_text}")
                yield f"[ERROR] 解析失败: {str(e)}\n"
                return

        if not data:
            yield "[ERROR] 生成内容校验未通过\n"
            return

        yield f"标题：{data['title']}\n"
        yield "[ARTICLE_JSON]" + json.dumps(data, ensure_ascii=False) + "\n"
    except Exception as e:
        logger.error(f"文章生成全流程失败: {str(e)}")
        yield f"[ERROR] 生成异常: {str(e)}\n"


# === 修改后的辅助函数 ===
def validate_and_fix_data(data, source_urls):
    """
    辅助函数：清洗数据，处理 AI 格式抽风的情况
    """
    if not isinstance(data, dict):
        return None
    
    # 1. Key 映射 (容错处理：如果 AI 返回了中文 Key，映射回英文)
    title = data.get("title") or data.get("标题") or "未命名文章"
    summary = data.get("summary") or data.get("摘要") or "暂无摘要"
    content = data.get("content") or data.get("正文") or ""
    
    # 2. 类型转换 (容错处理：如果 AI 返回了列表，拼接成字符串)
    if isinstance(title, list):
        title = title[0] # 标题取第一个
        
    if isinstance(summary, list):
        summary = " ".join(str(x) for x in summary)
        
    if isinstance(content, list):
        # 如果正文是列表，用换行符拼起来
        content = "\n\n".join(str(x) for x in content)
        
    # 3. 兜底检查
    if not content.strip():
        # 如果此时内容还是空的，可能是数据结构太深，打印日志排查
        logger.error(f"数据清洗失败，原始数据: {data}")
        return None

    return {
        "title": str(title),
        "summary": str(summary),
        "content": str(content),
        "source_urls": source_urls 
    }