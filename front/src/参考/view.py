import json
import os
import shutil
import sys
from asyncio import get_event_loop

import chromadb
from chromadb import Settings
from flask import request, g, Response, stream_with_context
from langchain_community import document_loaders
from marshmallow import ValidationError
from starlette.responses import StreamingResponse

from common.ApiResponse import ApiResponse
from common.BaseResponse import BaseResponse
from common.ErrorCode import ErrorCode
from config import settings
from constant.CommonConstant import SORT_ORDER_DESC, SORT_ORDER_ASC
from constant.FileConstant import RAGFILEPATH, RAGEMBEDDINGPATH, RAGGRAPHPATH
from constant.UserConstant import DEFAULT_ROLE
from controller.AI.validate import queryFileResult
from controller.scoring_result.validate import param_error
from models import File, db
from utils.GenerateGraph import GenerateGraph
from utils.ThreadLocal import ThreadLocalUtil

from langchain_community.document_loaders import TextLoader, PyPDFLoader, CSVLoader, JSONLoader, \
    UnstructuredMarkdownLoader
from langchain_community.vectorstores import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

queryFile = queryFileResult()
def upload_file():
    # 检查是否有文件被上传
    if 'file' not in request.files:
        error_response = BaseResponse.from_error_code(ErrorCode.PARAMS_ERROR)
        return ApiResponse.error_from_baseResponse(
            baseResponse=error_response,
            data="文件未上传"
        )

    file = request.files['file']

    # 检查文件名是否为空
    if file.filename == '':
        error_response = BaseResponse.from_error_code(ErrorCode.PARAMS_ERROR)
        return ApiResponse.error_from_baseResponse(
            baseResponse=error_response,
            data="文件名为空"
        )

    # 保存文件到指定目录
    user_map = ThreadLocalUtil.get()
    id = str(user_map.get('id'))
    directory = os.path.join(RAGFILEPATH, id)  # 获取目录路径
    file_path = ''.join([RAGFILEPATH, id, "\\", file.filename])
    file_path = os.path.join(file_path)
    print("file_path", file_path)
    # 确保目录存在
    os.makedirs(directory, exist_ok=True)  # 如果目录不存在则创建，exist_ok=True 表示如果目录已存在不会报错
    file.save(file_path)
    new_file = File()
    new_file.file_name = file.filename
    new_file.create_user = user_map.get('id')
    db.session.add(new_file)
    db.session.commit()
    return ApiResponse.success(data=file_path)


def delete_all_file():
    user_map = ThreadLocalUtil.get()
    id = str(user_map.get('id'))
    directory = os.path.join(RAGFILEPATH, id)
    embed_dir = os.path.join(RAGEMBEDDINGPATH, id)
    if os.path.exists(directory):
        try:
            # 删除目录及其所有内容
            shutil.rmtree(directory)
            shutil.rmtree(embed_dir)
            db.session.query(File).filter_by(create_user=user_map.get('id')).delete()
            db.session.commit()
            return ApiResponse.success(data="删除成功!")
        except Exception as e:
            # 处理删除过程中可能出现的错误
            error_response = BaseResponse.from_error_code(ErrorCode.OPERATION_ERROR)
            return ApiResponse.error_from_baseResponse(baseResponse=error_response, data=f"删除目录时出错: {str(e)}")
    else:
        error_response = BaseResponse.from_error_code(ErrorCode.PARAMS_ERROR)
        return ApiResponse.error_from_baseResponse(baseResponse=error_response, data="删除目录不存在")


def delete_one_file():
    user_map = ThreadLocalUtil.get()
    id = str(user_map.get('id'))
    file_name = request.json.get('file_name')
    directory = os.path.join(RAGFILEPATH, id)
    file_path = os.path.join(directory, file_name)
    if os.path.exists(file_path):
        try:
            # 删除指定文件
            os.remove(file_path)
            file = db.session.query(File).filter(File.file_name == file_name).filter(File.create_user == int(id)).first()
            db.session.delete(file)
            db.session.commit()
            return ApiResponse.success(data="删除成功!")
        except Exception as e:
            # 处理删除过程中可能出现的错误
            error_response = BaseResponse.from_error_code(ErrorCode.OPERATION_ERROR)
            return ApiResponse.error_from_baseResponse(baseResponse=error_response, data=f"删除目录时出错: {str(e)}")
    else:
        error_response = BaseResponse.from_error_code(ErrorCode.PARAMS_ERROR)
        return ApiResponse.error_from_baseResponse(baseResponse=error_response, data="删除文件不存在")


def query_database_for_all(query_data, user_map, isMy: bool = True):
    pageSize = query_data.get('pageSize')
    current = query_data.get('current')

    if user_map.get('user_role') == DEFAULT_ROLE:
        if pageSize > 20:
            print("用户访问异常")
            errorResponse = BaseResponse.from_error_code(ErrorCode.PARAMS_ERROR)
            return ApiResponse.error_from_baseResponse(errorResponse, data="用户访问异常")
    query = File.query
    # 查询条件
    query_filed = {
        'id': lambda q, v: q.filter(File.id == v),
        'file_name': lambda q, v: q.filter(File.file_name.contains(v)),
        'isIndex': lambda q, v: q.filter(File.isIndex == v),
        'isDelete': lambda q, v: q.filter(File.isDelete == v),
    }
    # 构建查询
    for filed, condition_func in query_filed.items():
        value = query_data.get(filed)
        if value is not None:
            query = condition_func(query, value)
    # 给用户看到得是没有逻辑删除的
    if user_map.get('user_role') == DEFAULT_ROLE:
        query = query.filter(File.isDelete == 0)
    # 如果是给自己看的
    if isMy:
        query = query.filter(File.create_user == user_map.get('id'))
        # 排序字段
    sort_fields = {
        'id': File.id,
        'file_name': File.file_name,
        'create_time': File.create_time,
    }
    filed_name = query_data.get('sortField')
    if filed_name is not None:
        sortField = sort_fields.get(filed_name)
        sortOrder = query_data.get('sortOrder')
        if sortOrder == SORT_ORDER_DESC:
            sortField = sortField.desc()
        elif sortOrder == SORT_ORDER_ASC:
            sortField = sortField.asc()
        else:
            print("排序字段有误，参数校验失败")
            errorResponse = BaseResponse.from_error_code(ErrorCode.PARAMS_ERROR)
            return ApiResponse.error_from_baseResponse(errorResponse, data="排序字段有误，参数校验失败")
        query = query.order_by(sortField)
    return query.paginate(page=current, per_page=pageSize)

def list_file():
    try:
        query_data = queryFile.load(request.json)
    except ValidationError as err:
        print(f"分页查询参数出错：{err}")
        first_key, first_value = next(iter(err.messages.items()))
        return ApiResponse.error_from_baseResponse(
            baseResponse=param_error,
            data="分页查询参数出错"
        )
    except Exception as e:
        print(e)
        return ApiResponse.error_from_baseResponse(
            baseResponse=param_error,
            data="分页查询参数出错"
        )
    user_map = ThreadLocalUtil.get()
    id = str(user_map.get('id'))
    directory = os.path.join(RAGFILEPATH, id)
    if os.path.exists(directory):
        user_map = ThreadLocalUtil.get()
        pagination = query_database_for_all(query_data=query_data, user_map=user_map)
        # 2.4 返回结果
        base_data = {
            "total": pagination.total,
            "pages": pagination.pages,
            "current": pagination.page,
            "pageSize": pagination.per_page
        }
        base_data['file_result'] = [file.to_vo() for file in pagination.items]
        return ApiResponse.success(data=base_data)
    else:
        error_response = BaseResponse.from_error_code(ErrorCode.OPERATION_ERROR)
        return ApiResponse.success(data=None)


def get_loader(file_path):
    index = file_path.rfind('.')
    if index == -1:
        error_response = BaseResponse.from_error_code(ErrorCode.PARAMS_ERROR)
        return ApiResponse.error_from_baseResponse()
    tail = file_path[index + 1:]
    if tail == 'pdf':
        return PyPDFLoader(file_path=file_path)
    elif tail == 'csv':
        return CSVLoader(file_path=file_path, encoding='utf-8')
    elif tail == 'json':
        return JSONLoader(file_path=file_path)
    elif tail == 'md':
        return UnstructuredMarkdownLoader(file_path=file_path)
    elif tail == 'txt':
        return TextLoader(file_path=file_path, encoding='utf-8')
    else:
        return None


def generate_embeddings():
    file_path = request.json.get('file_path')
    index = file_path.rfind('\\')
    file_name = file_path[index + 1:]
    embeddings = DashScopeEmbeddings(
        model="text-embedding-v1",
        dashscope_api_key=settings.dashscope_api_key
    )
    user_map = getattr(g, 'user_map', {})
    id = str(user_map.get('id'))
    persist_directory = os.path.join(RAGEMBEDDINGPATH, id)
    if os.path.exists(file_path):
        try:
            os.makedirs(persist_directory, exist_ok=True)
            loader = get_loader(file_path)
            if loader is None:
                error_response = BaseResponse.from_error_code(ErrorCode.PARAMS_ERROR)
                return ApiResponse.error_from_baseResponse(baseResponse=error_response,
                                                           data="文件只能是pdf,csv,json,md,txt")
            documents = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            splitter = text_splitter.split_documents(documents)
            # 修正点：使用正确的参数传递方式
            dabs = Chroma.from_documents(splitter, embeddings, persist_directory=persist_directory)
            # dabs.persist()
            print("新数据库已创建")
            file = db.session.query(File).filter(File.file_name == file_name).filter(File.create_user == user_map.get('id')).first()
            file.isIndex = 1
            db.session.commit()
            return ApiResponse.success(data="新数据库已创建")
        except Exception as e:
            error_response = BaseResponse.from_error_code(ErrorCode.OPERATION_ERROR)
            print(e)
            return ApiResponse.error_from_baseResponse(baseResponse=error_response, data="索引建立失败")
    else:
        error_response = BaseResponse.from_error_code(ErrorCode.PARAMS_ERROR)
        return ApiResponse.error_from_baseResponse(baseResponse=error_response, data="未上传任何文件，无法建立索引")


def delete_embeddings():
    user_map = getattr(g, 'user_map', {})
    id = str(user_map.get('id'))
    persist_directory = os.path.join(RAGEMBEDDINGPATH, id)
    if os.path.exists(persist_directory):
        try:
            # 删除目录及其所有内容
            shutil.rmtree(persist_directory)
            return ApiResponse.success(data="删除成功!")
        except Exception as e:
            # 处理删除过程中可能出现的错误
            error_response = BaseResponse.from_error_code(ErrorCode.OPERATION_ERROR)
            return ApiResponse.error_from_baseResponse(baseResponse=error_response, data=f"删除目录时出错: {str(e)}")
    else:
        error_response = BaseResponse.from_error_code(ErrorCode.PARAMS_ERROR)
        return ApiResponse.error_from_baseResponse(baseResponse=error_response, data=f"删除目录不存在!")


async def based_on_embeddings_query():
    query = request.json.get('query')
    user_map = getattr(g, 'user_map', {})
    id = str(user_map.get('id'))
    persist_directory = os.path.join(RAGEMBEDDINGPATH, id)
    # 3. 初始化 LLM 和检索链
    llm = ChatOpenAI(
        model='deepseek-reasoner',
        openai_api_key=settings.deepseek_api_key,
        openai_api_base='https://api.deepseek.com'
    )
    # todo 这里需要根据用户的问题和已经载入数据库的文献进行cos向量匹配，查看是否需要使用知识库
    if os.path.exists(persist_directory):

        embeddings = DashScopeEmbeddings(
            model="text-embedding-v1",
            dashscope_api_key=settings.dashscope_api_key
        )
        db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        print("成功加载现有数据库")
        retriever = db.as_retriever(search_kwargs={"k": 3})
        template = """你是关于一个专业的教学助手或者秘书，能够根据知识库中的内容进行回答问题：
        {context}
        问题：{question}
        回答应简洁且准确，避免编造信息,并根据用户的query判断回答使用哪一种语言,如果搜索到相关资料，请在回答开始加上，"已搜索到相关用户资料"。
        如果没有搜索到,请先告知用户"根据你提供根据提供的知识库内容，未搜索到...",然后使用联网功能搜索相关信息，内容也应当丰富有效
        """
        prompt = ChatPromptTemplate.from_template(template)

        chain = (
                {"context": retriever, "question": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
        )
        print("成功加载相关向量数据库")
        response = chain.invoke(query)
        return ApiResponse.success(data=response)
    else:
        print("用户没有相关向量数据库,直接调用deepseek回答问题")
        template = """你是关于一个专业的教学助手或者秘书，能够联网和根据个人知识回答用户问题,
        问题：{question}
        回答部分第一句请加上 "用户没有加载过任何私人数据库,我将为你联网搜索"
        """
        prompt = ChatPromptTemplate.from_template(template)
        chain = (
                {"question": RunnablePassthrough()} |
                prompt |
                llm |
                StrOutputParser()
        )
        response = chain.invoke(query)
        return ApiResponse.success(data=response)


def ask_stream():
    data = request.json
    query = data.get('query')
    user_map = getattr(g, 'user_map', {})
    id = str(user_map.get('id'))
    persist_directory = os.path.join(RAGEMBEDDINGPATH, id)

    # 初始化LLM - 确保启用流式模式
    llm = ChatOpenAI(
        model='deepseek-reasoner',
        openai_api_key=settings.deepseek_api_key,
        openai_api_base='https://api.deepseek.com',
        streaming=True
    )

    async def async_generator():
        if os.path.exists(persist_directory):
            embeddings = DashScopeEmbeddings(
                model="text-embedding-v1",
                dashscope_api_key=settings.dashscope_api_key
            )
            db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
            print("成功加载现有数据库")
            retriever = db.as_retriever(search_kwargs={"k": 3})

            template = """你是关于一个专业的教学助手或者秘书，能够根据知识库中的内容进行回答问题：
            {context}
            问题：{question}
            回答应准确丰富，,并根据用户的query判断回答使用哪一种语言,如果搜索到相关资料，请在回答开始加上，"已搜索到相关用户资料"。
            如果没有搜索到,请先告知用户"根据你提供根据提供的知识库内容，未搜索到...",然后使用联网功能搜索相关信息，内容也应当丰富有效
            """
            prompt = ChatPromptTemplate.from_template(template)

            chain = (
                    {"context": retriever, "question": RunnablePassthrough()}
                    | prompt
                    | llm
                    | StrOutputParser()
            )
            async for chunk in chain.astream(query):
                yield chunk + "\n"
                print(chunk,end='')
        else:
            template = """你是关于一个专业的教学助手或者秘书，能够联网和根据个人知识回答用户问题,
                   问题：{question}
                   回答部分第一句请加上 "用户没有加载过任何私人数据库,我将为你联网搜索"
                   """
            prompt = ChatPromptTemplate.from_template(template)
            chain = (
                    {"question": RunnablePassthrough()} |
                    prompt |
                    llm |
                    StrOutputParser()
            )
            async for chunk in chain.astream(query):
                yield chunk + "\n"
                print(chunk,end='')

    def generate():
        loop = get_event_loop()
        agen = async_generator()
        while True:
            try:
                chunk = loop.run_until_complete(agen.__anext__())
                yield chunk
            except StopAsyncIteration:
                break

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


def ask_stream2():
    data = request.json
    query = data.get('query')
    user_map = getattr(g, 'user_map', {})
    id = str(user_map.get('id'))
    persist_directory = os.path.join(RAGEMBEDDINGPATH, id)

    # 初始化LLM - 确保启用流式模式
    llm = ChatOpenAI(
        model='deepseek-chat',
        openai_api_key=settings.deepseek_api_key,
        openai_api_base='https://api.deepseek.com',
        streaming=True
    )

    def generate():
        if os.path.exists(persist_directory):
            embeddings = DashScopeEmbeddings(
                model="text-embedding-v1",
                dashscope_api_key=settings.dashscope_api_key
            )
            db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
            print("成功加载现有数据库")
            retriever = db.as_retriever(search_kwargs={"k": 3})
            template = """你是关于一个专业的教学助手或者秘书,全称“格智学舟小助手”，能够根据知识库中的内容进行回答问题：
            在回答问题时，请先展示你的思考过程，然后给出最终答案。思考过程请使用"[思考过程]"作为前缀，答案请使用"[最终答案]"作为前缀。
            {context}
            问题：{question}
            回答应准确丰富，避免编造信息,并根据用户的query判断回答使用哪一种语言,如果搜索到相关资料，请在回答开始加上，"已搜索到相关用户资料"。
            如果没有搜索到,请先告知用户"根据你提供根据提供的知识库内容，未搜索到...",然后使用联网功能搜索相关信息，内容也应当丰富有效
            """
            prompt = ChatPromptTemplate.from_template(template)
            chain = (
                    {"context": retriever, "question": RunnablePassthrough()}
                    | prompt
                    | llm
                    | StrOutputParser()
            )
            ret = chain.stream(query)

            text = ""
            for _token in ret:
                token = _token
                yield token
                text += token
                print(token)
        else:
            template = """你是关于一个专业的教学助手或者秘书，能够联网和根据个人知识回答用户问题,
                              问题：{question}
                              回答部分第一句请加上 "用户没有加载过任何私人数据库,我将为你联网搜索"
                              """
            prompt = ChatPromptTemplate.from_template(template)
            chain = (
                    {"question": RunnablePassthrough()} |
                    prompt |
                    llm |
                    StrOutputParser()
            )
            ret = chain.stream(query)
            text = ""
            for _token in ret:
                token = _token
                yield token
                text += token
                print(token)

    return Response(generate(), mimetype="text/event-stream")

def generate_graph():
    file_path = request.json.get('file_path')
    first_index = file_path.rfind('\\')
    second_index = file_path.rfind('.')
    file_name = file_path[first_index + 1:second_index]
    try:
        triples_list = GenerateGraph.generateGraph(file_path=file_path)
        if (triples_list == None):
            print("三元组为空!")
            error_response = BaseResponse.from_error_code(ErrorCode.OPERATION_ERROR)
            return ApiResponse.error_from_baseResponse(baseResponse=error_response, data="创建知识地图失败")
        user_map = ThreadLocalUtil.get()
        id = str(user_map.get('id'))
        # D:\\python\\pythonprojects\\flask\\graphrag\\public\\graph\\1
        graph_path = os.path.join(RAGGRAPHPATH, id)
        # D:\\python\\pythonprojects\\flask\\graphrag\\public\\graph\\1\\LLM4.pdf
        graph_file_path = GenerateGraph.save(triples_list, graph_path, file_name)
        return ApiResponse.success(data=graph_file_path)
    except Exception as e:
        error_response = BaseResponse.from_error_code(ErrorCode.OPERATION_ERROR)
        print(e)
        return ApiResponse.error_from_baseResponse(baseResponse=error_response, data="创建知识地图失败")
