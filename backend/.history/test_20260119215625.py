import gradio as gr
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import traceback

# ==============================
# 1. 配置模型连接
# ==============================
API_BASE = "http://localhost:6006/v1"
API_KEY = "EMPTY"

# 初始化模型
llm = ChatOpenAI(
    openai_api_base=API_BASE,
    openai_api_key=API_KEY,
    model_name="qwen-huluwa",
    temperature=0.7,
    max_tokens=2048,
    streaming=True
)

SYSTEM_PROMPT = "You are a helpful assistant. Please answer in concise language."

# ==============================
# 2. 定义核心逻辑函数 (已修复报错)
# ==============================
def predict(message, history):
    print(f"DEBUG - 收到新消息: {message}")
    # 调试：打印一下 history 的第一项看看长什么样（如果有的话）
    if history and len(history) > 0:
        print(f"DEBUG - History item format: {type(history[0])} - {history[0]}")

    history_langchain_format = []
    
    if SYSTEM_PROMPT:
        history_langchain_format.append(SystemMessage(content=SYSTEM_PROMPT))
    
    # 【核心修复部分】
    # 原代码：for human, ai in history: -> 报错
    # 新代码：使用 try-except 或索引访问，兼容长度大于2的情况
    for item in history:
        try:
            # 1. 尝试作为列表/元组处理 (Gradio 默认格式)
            if isinstance(item, (list, tuple)):
                # 只取前两个元素，忽略后面可能多出来的 metadata
                human = item[0]
                ai = item[1]
            # 2. 尝试作为字典处理 (防止 Gradio 使用 messages 格式)
            elif isinstance(item, dict):
                # 这种情况比较复杂，通常 ChatInterface 不会混发，这里做个兜底
                continue 
            else:
                continue
            
            # 转换为字符串并清洗 None
            human_text = str(human) if human is not None else ""
            ai_text = str(ai) if ai is not None else ""
            
            if human_text:
                history_langchain_format.append(HumanMessage(content=human_text))
            if ai_text:
                history_langchain_format.append(AIMessage(content=ai_text))
                
        except Exception as e:
            print(f"处理历史记录单条出错: {item}, 错误: {e}")
            continue

    # 添加当前用户消息
    history_langchain_format.append(HumanMessage(content=str(message)))
    
    # 调用模型
    partial_message = ""
    try:
        for chunk in llm.stream(history_langchain_format):
            if chunk.content:
                partial_message += chunk.content
                yield partial_message
    except Exception as e:
        error_msg = f"❌ 模型调用错误: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        yield error_msg

# ==============================
# 3. 启动界面
# ==============================
# 显式指定 type="tuples" 确保 Gradio 行为符合预期 (部分新版本需要)
demo = gr.ChatInterface(
    fn=predict,
    title="🤖 Qwen-Huluwa Chatbot",
    description=f"正在连接本地模型端口: {API_BASE}",
    examples=["你好，请介绍一下你自己。", "写一段 Python 代码实现冒泡排序。", "讲个笑话。"],
    # theme="soft",
    # type="tuples" # 如果你的 Gradio 版本 > 4.0 建议加上这个参数，如果报错则删掉这行
)

if __name__ == "__main__":
    print(f"启动服务... 目标 API: {API_BASE}")
    demo.launch(server_name="0.0.0.0", server_port=7861, share=False)