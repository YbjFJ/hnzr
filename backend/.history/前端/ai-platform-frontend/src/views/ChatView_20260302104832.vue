<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useChatStore } from '../stores/chat';
import type { ChatSession } from '../types/chat';
import type { Article } from '../types/article';
import { favoriteApi } from '../services/api';
import MarkdownIt from 'markdown-it';

// ================= 初始化配置 =================

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: true
});

const router = useRouter();
const chatStore = useChatStore();
const messageInput = ref('');
const error = ref('');
const messagesContainer = ref<HTMLElement | null>(null);
const isSending = ref(false);

// 编辑会话标题相关状态
const editingSessionId = ref<string | null>(null);
const editSessionTitle = ref('');

// 知识库：用户选择的收藏文章（作为本条/下条消息的参考）
const selectedKnowledgeIds = ref<number[]>([]);
const knowledgeDrawerVisible = ref(false);
const favoritesList = ref<Article[]>([]);
const loadingFavorites = ref(false);
const tempKnowledgeSelection = ref<number[]>([]);

// ================= 工具函数 =================

// 渲染 Markdown
const renderMarkdown = (content: string) => {
  if (!content) return '';
  // 可以在这里添加一些自定义的预处理
  return md.render(content);
};

// 格式化时间
const formatTime = (dateString: string): string => {
  const date = new Date(dateString);
  return isNaN(date.getTime()) ? '' : date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
};

// 格式化日期
const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return '';
  
  const today = new Date();
  const isToday = date.getDate() === today.getDate() && 
                  date.getMonth() === today.getMonth() && 
                  date.getFullYear() === today.getFullYear();
                  
  return isToday ? formatTime(dateString) : date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
};

// ================= 交互逻辑 =================

// 滚动到底部
const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// 监听消息变化，自动滚动
watch(() => chatStore.messages, () => {
  scrollToBottom();
}, { deep: true });

// 加载会话列表
onMounted(async () => {
  await chatStore.fetchSessions();
  // 如果没有会话，可以不默认创建，让用户看到欢迎页
});

// 创建新会话
const createNewSession = async () => {
  try {
    await chatStore.createSession('新咨询会话');
    // 给输入框焦点（可选）
  } catch {
    showError('创建会话失败');
  }
};

// 删除会话
const deleteSession = async (sessionId: string) => {
  if (!confirm('确定要删除这个会话吗？')) return;
  try {
    await chatStore.deleteSession(sessionId);
  } catch {
    showError('删除失败');
  }
};

// 切换会话
const switchSession = (session: ChatSession) => {
  chatStore.switchSession(session);
};

// 开始编辑会话标题
const startEditSession = (session: ChatSession) => {
  editingSessionId.value = session.id;
  editSessionTitle.value = session.title || '';
};

// 保存会话标题
const saveSessionTitle = async () => {
  if (!editingSessionId.value || !editSessionTitle.value.trim()) return;
  
  try {
    await chatStore.updateSessionTitle(editingSessionId.value, editSessionTitle.value.trim());
    editingSessionId.value = null;
  } catch (err) {
    showError(err instanceof Error ? err.message : '更新会话标题失败');
  }
};

// 取消编辑会话标题
const cancelEditSession = () => {
  editingSessionId.value = null;
  editSessionTitle.value = '';
};

// 显示错误提示
const showError = (msg: string) => {
  error.value = msg;
  setTimeout(() => { error.value = ''; }, 3000);
};

// 发送消息（可携带当前选中的收藏作为知识库）
const sendMessage = async () => {
  const content = messageInput.value.trim();
  if (!content || !chatStore.currentSession || isSending.value || chatStore.loading) return;

  messageInput.value = '';
  isSending.value = true;
  const textarea = document.querySelector('.input-textarea') as HTMLTextAreaElement;
  if (textarea) textarea.style.height = 'auto';

  const refIds = selectedKnowledgeIds.value.length > 0 ? [...selectedKnowledgeIds.value] : undefined;
  try {
    await chatStore.sendMessage(content, refIds);
  } catch (err) {
    showError(err instanceof Error ? err.message : '发送消息失败');
    messageInput.value = content;
  } finally {
    isSending.value = false;
  }
};

// 打开知识库选择抽屉并加载收藏列表
const openKnowledgeDrawer = async () => {
  knowledgeDrawerVisible.value = true;
  tempKnowledgeSelection.value = [...selectedKnowledgeIds.value];
  loadingFavorites.value = true;
  try {
    const res = await favoriteApi.getFavorites({ page: 1, page_size: 200 });
    favoritesList.value = res.data.items || [];
  } catch {
    favoritesList.value = [];
  } finally {
    loadingFavorites.value = false;
  }
};

// 确认知识库选择
const confirmKnowledgeSelection = () => {
  selectedKnowledgeIds.value = [...tempKnowledgeSelection.value];
  knowledgeDrawerVisible.value = false;
};

// 全选 / 取消全选
const selectAllFavorites = () => {
  tempKnowledgeSelection.value = favoritesList.value.map((a) => a.id);
};
const clearKnowledgeSelection = () => {
  tempKnowledgeSelection.value = [];
};

// 清空当前会话选中的知识库
const clearSelectedKnowledge = () => {
  selectedKnowledgeIds.value = [];
};

// 处理输入框回车
const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault(); // 阻止默认换行
    sendMessage();
  }
};

// 输入框自适应高度
const autoResize = (e: Event) => {
  const target = e.target as HTMLTextAreaElement;
  target.style.height = 'auto';
  target.style.height = target.scrollHeight + 'px';
};
</script>

<template>
  <div class="chat-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <button type="button" class="sidebar-back-btn" @click="router.push('/')" title="返回首页">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
          返回
        </button>
        <div class="logo-area">
          <div class="logo-icon">AgFi</div> <!-- Agriculture & Finance -->
          <h2>智农金信 AI</h2>
        </div>
        <button class="new-chat-btn" @click="createNewSession">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          新建会话
        </button>
      </div>
      
      <div class="session-list">
        <div 
          v-for="session in chatStore.sessions" 
          :key="session.id"
          class="session-item"
          :class="{ active: chatStore.currentSession?.id === session.id }"
          @click="switchSession(session)"
        >
          <div class="session-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
          </div>
          
          <div class="session-info">
            <!-- 编辑状态 -->
            <div v-if="editingSessionId === session.id" class="session-title-edit">
              <input 
                type="text" 
                v-model="editSessionTitle"
                class="session-title-input"
                @keyup.enter="saveSessionTitle"
                @keyup.escape="cancelEditSession"
                @blur="saveSessionTitle"
                ref="focusInput"
                placeholder="会话标题"
              />
            </div>
            <!-- 显示状态 -->
            <div v-else class="session-title-wrapper">
              <h3 class="session-title">{{ session.title || '新会话' }}</h3>
              <span class="session-time">{{ formatDate(session.created_at) }}</span>
            </div>
          </div>
          
          <div class="session-actions">
            <button 
              class="edit-btn" 
              @click.stop="startEditSession(session)" 
              title="编辑会话"
              v-if="editingSessionId !== session.id"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
            </button>
            <button class="delete-btn" @click.stop="deleteSession(session.id)" title="删除会话">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </div>
        </div>
      </div>
    </aside>
    
    <!-- 主聊天区域 -->
    <main class="main-content">
      <template v-if="chatStore.currentSession">
        <header class="chat-header">
          <div class="header-title-area">
            <!-- 聊天头部编辑状态 -->
            <div v-if="editingSessionId === chatStore.currentSession?.id" class="header-title-edit">
              <input 
                type="text" 
                v-model="editSessionTitle"
                class="header-title-input"
                @keyup.enter="saveSessionTitle"
                @keyup.escape="cancelEditSession"
                @blur="saveSessionTitle"
                ref="focusInput"
                placeholder="会话标题"
              />
            </div>
            <!-- 聊天头部显示状态 -->
            <h3 v-else class="header-title" @click="startEditSession(chatStore.currentSession)">
              {{ chatStore.currentSession.title }}
              <span class="edit-icon">✏️</span>
            </h3>
          </div>
          <div class="header-actions">
            <!-- 这里可以放导出报告等按钮 -->
          </div>
        </header>
        
        <div class="messages-scroll-area" ref="messagesContainer">
          <div class="messages-wrapper">
            <!-- 欢迎提示（如果消息为空） -->
            <div v-if="chatStore.messages.length === 0" class="empty-state-hint">
              <div class="hint-icon">💡</div>
              <p>您可以问我关于 <b>农业政策补贴</b>、<b>农产品期货</b>、<b>农村信贷</b> 等问题。</p>
            </div>

            <div 
              v-for="message in chatStore.messages" 
              :key="message.id"
              class="message-row"
              :class="message.role"
            >
              <div class="avatar">
                <span v-if="message.role === 'user'">我</span>
                <span v-else>AI</span>
              </div>
              
              <div class="message-bubble">
                <div class="bubble-content markdown-body" v-html="renderMarkdown(message.content)"></div>
                <!-- 流式传输时的光标 -->
                <span v-if="message.role === 'ai' && chatStore.loading && message === chatStore.messages[chatStore.messages.length -1]" class="typing-cursor"></span>
                <div class="message-meta">{{ formatTime(message.created_at) }}</div>
              </div>
            </div>
            
            <!-- 底部占位，防止内容被输入框遮挡 -->
            <div style="height: 20px;"></div>
          </div>
        </div>

        <div class="input-area-wrapper">
          <div v-if="error" class="error-toast">{{ error }}</div>
          
          <div class="knowledge-bar">
            <button type="button" class="knowledge-btn" @click="openKnowledgeDrawer">
              <span class="knowledge-btn-icon">📚</span>
              选择知识库
            </button>
            <span v-if="selectedKnowledgeIds.length > 0" class="knowledge-hint">
              已选 {{ selectedKnowledgeIds.length }} 篇收藏作为知识库
              <button type="button" class="knowledge-clear" @click="clearSelectedKnowledge">清空</button>
            </span>
          </div>
          <div class="input-box">
            <textarea 
              v-model="messageInput"
              class="input-textarea"
              placeholder="请输入您的问题... (Shift + Enter 换行)"
              rows="1"
              @keydown="handleKeydown"
              @input="autoResize"
              :disabled="chatStore.loading"
            ></textarea>
            <button 
              class="send-btn" 
              @click="sendMessage"
              :disabled="!messageInput.trim() || chatStore.loading"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
          </div>
          <div class="footer-note">内容由 AI 生成，仅供参考，不构成投资建议。</div>

          <!-- 知识库选择抽屉 -->
          <el-drawer
            v-model="knowledgeDrawerVisible"
            title="选择收藏文章作为知识库"
            direction="rtl"
            size="400px"
            :with-header="true"
          >
            <p class="drawer-desc">选择一篇或多篇收藏，AI 将优先基于这些文章回答您的问题。不选则使用全局知识库检索。</p>
            <div class="drawer-actions">
              <el-button size="small" @click="selectAllFavorites">全选</el-button>
              <el-button size="small" @click="clearKnowledgeSelection">取消全选</el-button>
              <el-button type="primary" size="small" @click="confirmKnowledgeSelection">确定</el-button>
            </div>
            <div v-loading="loadingFavorites" class="favorites-list">
              <template v-if="favoritesList.length === 0 && !loadingFavorites">
                <p class="empty-favorites">暂无收藏，请先在文章页收藏后再选为知识库。</p>
              </template>
              <el-checkbox-group v-else v-model="tempKnowledgeSelection" class="checkbox-group">
                <div v-for="article in favoritesList" :key="article.id" class="favorite-item">
                  <el-checkbox :label="article.id">
                    <span class="favorite-item-title">{{ article.title }}</span>
                  </el-checkbox>
                </div>
              </el-checkbox-group>
            </div>
          </el-drawer>
        </div>
      </template>
      
      <!-- 空状态（未选择会话） -->
      <div v-else class="welcome-screen">
        <div class="welcome-content">
          <div class="welcome-logo">🌾</div>
          <h1>智农金信 AI 咨询助手</h1>
          <p class="subtitle">专业的农业与金融领域智能分析平台</p>
          
          <div class="features-grid">
            <div class="feature-card">
              <div class="icon">📊</div>
              <h4>市场分析</h4>
              <p>获取最新的农产品价格趋势与金融市场动态</p>
            </div>
            <div class="feature-card">
              <div class="icon">📜</div>
              <h4>政策解读</h4>
              <p>深度解析农业补贴政策与金融扶持法规</p>
            </div>
            <div class="feature-card">
              <div class="icon">🤖</div>
              <h4>智能问答</h4>
              <p>基于 RAG 技术提供准确的专业知识问答</p>
            </div>
          </div>
          
          <button class="start-chat-btn" @click="createNewSession">开始新的咨询</button>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ================= 布局样式 ================= */
.chat-layout {
  display: flex;
  height: 100vh;
  width: 100%;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
  overflow: hidden;
}

/* ================= 侧边栏 ================= */
.sidebar {
  width: 300px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  box-shadow: 4px 0 20px rgba(0, 0, 0, 0.05);
  animation: slideInLeft 0.5s ease-out;
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.sidebar-header {
  padding: 24px;
  border-bottom: 2px solid rgba(102, 126, 234, 0.1);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.02), rgba(118, 75, 162, 0.02));
}

.sidebar-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #667eea;
  background: rgba(102, 126, 234, 0.08);
  border: 1px solid rgba(102, 126, 234, 0.2);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-weight: 500;
}

.sidebar-back-btn:hover {
  background: rgba(102, 126, 234, 0.15);
  border-color: #667eea;
  color: #764ba2;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.logo-icon {
  width: 38px;
  height: 38px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 11px;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

.logo-area h2 {
  font-size: 18px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0;
  letter-spacing: -0.5px;
}

.new-chat-btn {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.new-chat-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 6px;
  border-radius: 12px;
  cursor: pointer;
  color: #5a5e66;
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  position: relative;
  overflow: hidden;
}

.session-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 3px;
  height: 100%;
  background: linear-gradient(180deg, #667eea, #764ba2);
  transform: scaleY(0);
  transition: transform 0.3s ease;
}

.session-item:hover {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08), rgba(118, 75, 162, 0.08));
  transform: translateX(5px);
}

.session-item:hover::before {
  transform: scaleY(1);
}

.session-item.active {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.15));
  color: #667eea;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}

.session-item.active::before {
  transform: scaleY(1);
}

.session-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 140px;
}

.session-time {
  font-size: 11px;
  color: #9ca3af;
  font-weight: 500;
}

.session-icon {
  opacity: 0.6;
  transition: opacity 0.3s ease;
}

.session-item:hover .session-icon {
  opacity: 1;
}

.session-actions {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.edit-btn,
.delete-btn {
  margin-left: auto;
  background: none;
  border: none;
  color: #9ca3af;
  padding: 4px;
  cursor: pointer;
  opacity: 0;
  transition: all 0.3s ease;
  border-radius: 6px;
}

.session-item:hover .edit-btn,
.session-item:hover .delete-btn {
  opacity: 1;
}

.edit-btn:hover {
  color: #667eea;
  background: rgba(102, 126, 234, 0.1);
}

.delete-btn:hover {
  color: #dc2626;
  background: rgba(220, 38, 38, 0.1);
}

.session-title-edit {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-title-input {
  flex: 1;
  padding: 6px 10px;
  border: 2px solid #667eea;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #2c3e50;
  background: white;
  outline: none;
  transition: all 0.3s ease;
}

.session-title-input:focus {
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
}

.session-title-wrapper {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* ================= 主区域 ================= */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background: white;
  margin: 20px;
  border-radius: 20px;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  animation: fadeIn 0.6s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.chat-header {
  height: 70px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
  border-bottom: 2px solid rgba(102, 126, 234, 0.1);
  padding: 0 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title {
  font-size: 18px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: color 0.3s ease;
}

.header-title:hover {
  color: #667eea;
}

.edit-icon {
  font-size: 14px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.header-title:hover .edit-icon {
  opacity: 1;
}

.header-title-edit {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.header-title-input {
  flex: 1;
  padding: 10px 16px;
  border: 2px solid #667eea;
  border-radius: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #2c3e50;
  background: white;
  outline: none;
  transition: all 0.3s ease;
  min-width: 200px;
}

.header-title-input:focus {
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
}

/* ================= 消息列表 ================= */
.messages-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 28px 0;
  scroll-behavior: smooth;
}

.messages-wrapper {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 28px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.message-row {
  display: flex;
  gap: 16px;
  animation: fadeInUp 0.4s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-row.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.message-row.ai .avatar {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
}

.message-row.user .avatar {
  background: linear-gradient(135deg, #059669, #10b981);
  color: white;
}

.message-bubble {
  max-width: 70%;
  display: flex;
  flex-direction: column;
}

.bubble-content {
  padding: 16px 20px;
  border-radius: 16px;
  font-size: 15px;
  line-height: 1.7;
  position: relative;
  word-wrap: break-word;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.message-row.ai .bubble-content {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
  color: #2c3e50;
  border: 2px solid rgba(102, 126, 234, 0.1);
  border-top-left-radius: 4px;
}

.message-row.user .bubble-content {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border-top-right-radius: 4px;
}

.message-meta {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 6px;
  align-self: flex-start;
  font-weight: 500;
}

.message-row.user .message-meta {
  align-self: flex-end;
  color: rgba(255, 255, 255, 0.7);
}

/* ================= 输入区域 ================= */
.input-area-wrapper {
  background: white;
  border-top: 2px solid rgba(102, 126, 234, 0.1);
  padding: 24px 28px;
  position: relative;
}

.knowledge-bar {
  max-width: 900px;
  margin: 0 auto 10px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.knowledge-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 13px;
  color: #667eea;
  background: rgba(102, 126, 234, 0.08);
  border: 1px solid rgba(102, 126, 234, 0.25);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-weight: 500;
}

.knowledge-btn:hover {
  background: rgba(102, 126, 234, 0.15);
  border-color: #667eea;
}

.knowledge-btn-icon {
  font-size: 14px;
}

.knowledge-hint {
  font-size: 12px;
  color: #6b7280;
}

.knowledge-clear {
  margin-left: 8px;
  padding: 0 6px;
  font-size: 12px;
  color: #667eea;
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}

.knowledge-clear:hover {
  color: #764ba2;
}

.drawer-desc {
  font-size: 13px;
  color: #6b7280;
  margin: 0 0 16px;
  line-height: 1.6;
}

.drawer-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.favorites-list {
  min-height: 120px;
}

.favorites-list .checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.favorite-item {
  padding: 8px 10px;
  border-radius: 10px;
  background: #f9fafb;
  transition: background 0.2s;
}

.favorite-item:hover {
  background: #f3f4f6;
}

.favorite-item-title {
  font-size: 13px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.empty-favorites {
  font-size: 13px;
  color: #9ca3af;
  text-align: center;
  padding: 24px 16px;
  margin: 0;
}

.input-box {
  max-width: 900px;
  margin: 0 auto;
  position: relative;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  transition: all 0.3s ease;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.input-box:focus-within {
  border-color: #667eea;
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
}

.input-textarea {
  flex: 1;
  border: none;
  background: transparent;
  resize: none;
  font-size: 15px;
  line-height: 1.6;
  padding: 0;
  max-height: 200px;
  outline: none;
  color: #2c3e50;
  font-weight: 400;
}

.send-btn {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
}

.send-btn:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
  box-shadow: none;
}

.footer-note {
  text-align: center;
  font-size: 12px;
  color: #9ca3af;
  margin-top: 12px;
  font-weight: 500;
}

/* ================= 欢迎屏幕 ================= */
.welcome-screen {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.02), rgba(118, 75, 162, 0.02));
}

.welcome-content {
  text-align: center;
  max-width: 700px;
  padding: 60px 40px;
}

.welcome-logo {
  font-size: 72px;
  margin-bottom: 28px;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-15px);
  }
}

.welcome-content h1 {
  font-size: 36px;
  color: #2c3e50;
  margin-bottom: 16px;
  font-weight: 800;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  color: #6b7280;
  margin-bottom: 50px;
  font-size: 18px;
  font-weight: 500;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  margin-bottom: 50px;
}

.feature-card {
  background: white;
  padding: 28px;
  border-radius: 16px;
  border: 2px solid rgba(102, 126, 234, 0.1);
  text-align: center;
  transition: all 0.3s ease;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
}

.feature-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 12px 32px rgba(102, 126, 234, 0.2);
  border-color: rgba(102, 126, 234, 0.3);
}

.feature-card .icon {
  font-size: 36px;
  margin-bottom: 16px;
}

.feature-card h4 {
  margin: 0 0 10px 0;
  color: #2c3e50;
  font-weight: 700;
  font-size: 18px;
}

.feature-card p {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
  line-height: 1.6;
}

.start-chat-btn {
  padding: 14px 40px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
  border-radius: 25px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.3);
}

.start-chat-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(102, 126, 234, 0.4);
}

.empty-state-hint {
  text-align: center;
  color: #6b7280;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
  padding: 24px;
  border-radius: 12px;
  font-size: 15px;
  border: 2px solid rgba(102, 126, 234, 0.1);
}

.hint-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

/* ================= Markdown 内容样式 ================= */
:deep(.markdown-body) {
  font-family: inherit;
}

:deep(.markdown-body p) {
  margin-bottom: 12px;
}

:deep(.markdown-body p:last-child) {
  margin-bottom: 0;
}

:deep(.markdown-body strong) {
  font-weight: 700;
  color: #667eea;
}

:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3) {
  margin-top: 20px;
  margin-bottom: 10px;
  font-weight: 700;
  line-height: 1.4;
  color: #2c3e50;
}

:deep(.markdown-body h3) {
  font-size: 1.15em;
}

:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  padding-left: 24px;
  margin-bottom: 12px;
}

:deep(.markdown-body li) {
  margin-bottom: 6px;
}

:deep(.markdown-body blockquote) {
  margin: 16px 0;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08), rgba(118, 75, 162, 0.08));
  border-left: 4px solid #667eea;
  border-radius: 8px;
  color: #4a5568;
  font-size: 14px;
}

:deep(.markdown-body blockquote strong) {
  color: #4a5568;
}

:deep(.markdown-body hr) {
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.3), transparent);
  border: none;
  margin: 20px 0;
}

:deep(.markdown-body a) {
  color: #667eea;
  text-decoration: none;
  font-weight: 600;
  border-bottom: 1px solid transparent;
  transition: all 0.3s ease;
}

:deep(.markdown-body a:hover) {
  border-bottom-color: #667eea;
  color: #764ba2;
}

/* 用户消息样式覆盖 */
.message-row.user :deep(.markdown-body) {
  color: white;
}

.message-row.user :deep(.markdown-body strong) {
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.message-row.user :deep(.markdown-body a) {
  color: #e0e7ff;
}

.message-row.user :deep(.markdown-body blockquote) {
  background: rgba(255, 255, 255, 0.15);
  border-left-color: rgba(255, 255, 255, 0.3);
}

/* 打字机光标动画 */
.typing-cursor::after {
  content: '▋';
  display: inline-block;
  color: #667eea;
  animation: blink 1s step-end infinite;
  margin-left: 2px;
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

.error-toast {
  position: absolute;
  top: -50px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, rgba(220, 38, 38, 0.95), rgba(239, 68, 68, 0.95));
  color: white;
  padding: 12px 20px;
  border-radius: 25px;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 6px 20px rgba(220, 38, 38, 0.3);
  animation: slideInDown 0.4s ease-out;
}

/* ================= 响应式设计 ================= */
@media (max-width: 1024px) {
  .sidebar {
    width: 260px;
  }

  .features-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .chat-layout {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    height: auto;
    max-height: 40vh;
  }

  .main-content {
    margin: 0;
    border-radius: 0;
  }

  .message-bubble {
    max-width: 85%;
  }

  .welcome-content {
    padding: 30px 20px;
  }

  .welcome-content h1 {
    font-size: 28px;
  }
}
</style>