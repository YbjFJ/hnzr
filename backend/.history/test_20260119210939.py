from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# 1. 配置连接信息
# 如果你用了 SSH 隧道，地址就是 localhost:6006
# 如果用了 AutoDL 自定义服务，地址就是那个公网 URL
API_BASE = "http://localhost:6006/v1" 
API_KEY = "EMPTY"  # 本地部署通常不需要 Key，随便填

# 2. 初始化模型
chat = ChatOpenAI(
    openai_api_base=API_BASE,
    openai_api_key=API_KEY,
    model_name="gpt-3.5-turbo", # 这里名字随便填，因为服务端其实只跑了一个模型
    temperature=0.7,
    max_tokens=512
)

# 3. 开始对话
messages = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="你是谁？")
]

# 4. 调用
response = chat.invoke(messages)

print("-" * 20)
print(response.content)
print("-" * 20)