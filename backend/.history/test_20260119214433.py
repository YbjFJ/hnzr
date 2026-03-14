import gradio as gr
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# ==============================
# 1. 配置模型连接
# ==============================
API_BASE = "http://localhost:6006/v1"
API_KEY = "EMPTY"

# 初始化模型
# 注意：这里开启了 streaming=True，以便在网页上实现打字机效果
llm = ChatOpenAI(
    openai_api_base=API_BASE,
    openai_api_key=API_KEY,
    model_name="gpt-3.5-turbo",
    temperature=0.7,
    max_tokens=2048, # 网页端通常可以设置大一点
    streaming=True   # 关键参数：启用流式输出
)

# 系统提示词
SYSTEM_PROMPT = "You are a helpful assistant. Please answer in concise language."

# ==============================
# 2. 定义核心逻辑函数
# ==============================
def predict(message, history):
    """
    message: 当前用户输入的消息 (str)
    history: 之前的对话历史，格式为 [[user_msg, bot_msg], ...]
    """
    
    # 1. 构建 LangChain 需要的消息列表
    # 先放入系统提示词
    history_langchain_format = [SystemMessage(content=SYSTEM_PROMPT)]
    
    # 遍历 Gradio 传来的历史记录，转换成 LangChain 的对象
    for human, ai in history:
        history_langchain_format.append(HumanMessage(content=human))
        history_langchain_format.append(AIMessage(content=ai))
    
    # 最后放入当前用户的输入
    history_langchain_format.append(HumanMessage(content=message))
    
    # 2. 调用模型并流式返回
    partial_message = ""
    try:
        # 使用 .stream() 方法获取流式响应
        for chunk in llm.stream(history_langchain_format):
            if chunk.content:
                partial_message += chunk.content
                # yield 把当前累积的文本返回给前端，实现打字机效果
                yield partial_message
    except Exception as e:
        yield f"Error: {str(e)}\n请检查 API 地址 {API_BASE} 是否可连接。"

# ==============================
# 3. 构建 Gradio 界面
# ==============================
# demo = gr.ChatInterface(
#     fn=predict,
#     title="🤖 Local LLM Chatbot",
#     description=f"正在连接本地模型: {API_BASE}",
#     theme="soft", # 可选主题: 'default', 'soft', 'glass'
#     examples=["你好，请介绍一下你自己。", "写一段 Python 代码实现冒泡排序。", "讲个笑话。"],
#     retry_btn="重试",
#     undo_btn="撤回",
#     clear_btn="清空对话",
# )

# ==============================
# 4. 启动服务
# ==============================
if __name__ == "__main__":
    # server_name="0.0.0.0" 允许局域网访问
    # server_port=7860 是默认端口
    print(f"正在启动 Gradio 服务，目标 API: {API_BASE}")
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)