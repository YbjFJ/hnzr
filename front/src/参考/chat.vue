<template>
  <el-card class="page-container">
    <div class="dialog-container">
      <div class="chat-messages">
        <div
            v-for="(message, index) in messages"
            :key="index"
            :class="{
            'user-message': message.sender === 'user',
           'model-message': message.sender ==='model',
          }"
        >
          <span v-if="message.sender === 'model'">Agent <br/></span>
          <span v-if="message.sender === 'user'"> User  <br/></span>
          {{ message.content }}
        </div>
      </div>
      <div class="input-container">
        <el-input
            v-model="inputMessage"
            @keyup.enter="sendMessage"
            placeholder="请输入你的问题"
            style="flex: 1; margin-right: 15px; height: 50px;"
        />
        <el-button @click="sendMessage" type="primary">发送</el-button>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import {ref} from "vue";
import {ElCard, ElInput, ElButton} from "element-plus";
import {chat} from "@/api/chat.js";

const messages = ref([
  {sender: "model", content: "你好！有什么我可以帮忙的吗？"},
]);
const inputMessage = ref("");

const sendMessage = () => {
  if (inputMessage.value.trim() === "") return;
  messages.value.push({sender: "user", content: inputMessage.value});
  const question = inputMessage.value;
  console.log(question);
  // 模拟大模型回复
  setTimeout(async () => {
    const response = await chat(question, "query");
    messages.value.push({sender: "model", content: response});
  }, 1000);
  inputMessage.value = "";
};
</script>

<style scoped>
/* 使el-card占据右侧屏幕中间位置 */
.page-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #e6f7ff; /* 淡蓝色背景 */
  font-family: Arial, sans-serif; /* 设置字体 */
}

.dialog-container {
  width: 800px;
  height: 600px;
  border: 1px solid #ccc;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  background-color: white;
  display: flex;
  flex-direction: column;
  justify-content: space-between; /* 新增，让子元素在垂直方向两端对齐 */
}

.chat-messages {
  height: auto;
  overflow-y: auto;
  margin-bottom: 20px;
}

.input-container {
  display: flex;
  align-items: center;
  height: 50px; /* 调整为和输入框高度一致 */
}

.chat-messages div {
  margin-bottom: 12px;
  opacity: 0;
  animation: fadeIn 0.5s ease-in-out forwards;
}

.user-message {
  text-align: left; /* 文字左对齐 */
  color: white;
  background-color: #42a5f5;
  border-radius: 15px;
  padding: 10px 15px;
  display: inline-block;
  max-width: 75%;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  float: right; /* 让气泡靠右显示 */
}

.model-message {
  text-align: left;
  color: #333;
  background-color: #f0f9ff; /* 浅蓝灰色气泡 */
  border-radius: 15px;
  padding: 10px 15px;
  display: inline-block;
  max-width: 75%;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); /* 消息气泡阴影 */
}

.input-container button {
  padding: 12px 20px;
  width: auto;
  background-color: #42a5f5;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.3s ease;
  height: 50px; /* 调整为和输入框高度一致 */
}

.input-container button:hover {
  background-color: #1976d2; /* 按钮悬停颜色 */
}

@keyframes fadeIn {
  to {
    opacity: 1;
  }
}
</style>