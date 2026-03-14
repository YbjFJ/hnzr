import { defineStore } from 'pinia';
import type { ChatSession, ChatMessage, AnalysisReport } from '../types/chat';
import { MessageRole } from '../types/chat';
import { chatApi, reportApi } from '../services/api';

export const useChatStore = defineStore('chat', {
  state: () => ({
    // 会话列表
    sessions: [] as ChatSession[],
    // 当前选中的会话
    currentSession: null as ChatSession | null,
    // 当前会话的消息列表
    messages: [] as ChatMessage[],
    // 分析报告列表
    reports: [] as AnalysisReport[],
    // 全局加载状态
    loading: false,
    // 错误信息
    error: null as string | null
  }),

  getters: {
    // 获取当前会话的所有消息
    currentSessionMessages: (state) => state.messages,
    // 判断当前是否已选择会话
    hasActiveSession: (state) => !!state.currentSession,
  },

  actions: {
    /**
     * 获取会话列表
     */
    async fetchSessions() {
      this.loading = true;
      this.error = null;
      try {
        const sessions = await chatApi.getSessions();
        this.sessions = sessions;
        // 如果当前没有选中会话且列表不为空，可选：自动选中第一个
        // if (!this.currentSession && sessions.length > 0) {
        //   this.switchSession(sessions[0]);
        // }
        return sessions;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '获取会话列表失败';
        console.error('Fetch sessions error:', err);
        throw err;
      } finally {
        this.loading = false;
      }
    },

    /**
     * 创建新会话
     * @param title 可选的会话标题
     */
    async createSession(title?: string) {
      this.loading = true;
      this.error = null;
      try {
        const session = await chatApi.createSession(title);
        // 将新会话添加到列表头部
        this.sessions.unshift(session);
        // 自动切换到新会话
        this.currentSession = session;
        this.messages = [];
        return session;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '创建会话失败';
        console.error('Create session error:', err);
        throw err;
      } finally {
        this.loading = false;
      }
    },

    /**
     * 删除会话
     * @param sessionId 会话ID
     */
    async deleteSession(sessionId: string) {
      // 这里的 loading 可能会导致 UI 闪烁，可视情况移除或使用专门的 deletingId 状态
      try {
        await chatApi.deleteSession(sessionId);
        
        // 从列表中移除
        this.sessions = this.sessions.filter(session => session.id !== sessionId);
        
        // 如果删除的是当前选中的会话，清空当前会话状态
        if (this.currentSession?.id === sessionId) {
          this.currentSession = null;
          this.messages = [];
        }
      } catch (err) {
        this.error = err instanceof Error ? err.message : '删除会话失败';
        console.error('Delete session error:', err);
        throw err;
      }
    },
    
    /**
     * 更新会话标题
     * @param sessionId 会话ID
     * @param title 新的会话标题
     */
    async updateSessionTitle(sessionId: string, title: string) {
      try {
        const updatedSession = await chatApi.updateSession(sessionId, title);
        
        // 更新列表中的会话
        const index = this.sessions.findIndex(session => session.id === sessionId);
        if (index !== -1) {
          this.sessions[index] = updatedSession;
        }
        
        // 如果是当前选中的会话，也更新当前会话
        if (this.currentSession?.id === sessionId) {
          this.currentSession = updatedSession;
        }
        
        return updatedSession;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '更新会话标题失败';
        console.error('Update session title error:', err);
        throw err;
      }
    },
    
    /**
     * 切换当前会话
     * @param session 目标会话对象
     */
    switchSession(session: ChatSession) {
      // 如果点击的是当前会话，不做处理
      if (this.currentSession?.id === session.id) return;

      this.currentSession = session;
      this.messages = []; // 切换时先清空消息，避免显示旧数据
      this.error = null;
      this.fetchMessages(session.id);
    },

    /**
     * 获取指定会话的消息记录
     * @param sessionId 会话ID
     */
    async fetchMessages(sessionId: string) {
      this.loading = true;
      this.error = null;
      try {
        const messages = await chatApi.getMessages(sessionId);
        
        // 只有当获取的消息属于当前选中的会话时才更新 state
        // 防止网络延迟导致切换会话后显示了上一个会话的消息
        if (this.currentSession?.id === sessionId) {
          this.messages = messages;
        }
        return messages;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '获取消息失败';
        console.error('Fetch messages error:', err);
        throw err;
      } finally {
        this.loading = false;
      }
    },

    /**
     * 发送消息（流式响应）
     * @param content 用户输入的内容
     * @param refArticleIds 可选，作为本条消息知识库的收藏文章 ID 列表
     */
    async sendMessage(content: string, refArticleIds?: number[]) {
      if (!this.currentSession) {
        const errorMsg = '请先创建或选择一个会话';
        this.error = errorMsg;
        throw new Error(errorMsg);
      }

      this.loading = true;
      this.error = null;

      // 生成临时 ID (转换为字符串以适配通常的 UUID 类型)
      const tempUserId = Date.now().toString();
      const tempAiId = (Date.now() + 1).toString();
      
      try {
        // 1. 乐观更新：立即添加用户消息
        const userMessage: ChatMessage = {
          id: tempUserId, 
          session_id: this.currentSession.id,
          role: MessageRole.USER,
          content: content,
          ref_article_ids: undefined, // 或 null，取决于后端定义
          created_at: new Date().toISOString()
        };
        
        this.messages.push(userMessage);
        
        // 2. 乐观更新：立即添加 AI 占位消息
        const tempAiMessage: ChatMessage = {
          id: tempAiId,
          session_id: this.currentSession.id,
          role: MessageRole.AI,
          content: '', // 初始为空，等待流式填充
          ref_article_ids: undefined,
          created_at: new Date().toISOString()
        };
        
        this.messages.push(tempAiMessage);
        
        // 3. 调用 API 进行流式传输（可传入收藏文章 ID 作为知识库）
        await chatApi.sendMessageStream(
          this.currentSession.id,
          content,
          (chunk: string) => {
            const aiMessage = this.messages.find(m => m.id === tempAiId);
            if (aiMessage) {
              aiMessage.content += chunk;
            }
          },
          () => {
            this.loading = false;
            
            // 4. 同步数据：流结束后刷新消息列表
            // 目的：获取后端生成的真实 UUID、引用文章ID等完整信息
            // 延迟 500ms 确保后端数据库事务已提交
            setTimeout(async () => {
              if (this.currentSession) {
                await this.fetchMessages(this.currentSession.id);
              }
            }, 500);
          },
          refArticleIds
        );
        
      } catch (err) {
        this.error = err instanceof Error ? err.message : '发送消息失败';
        this.loading = false;
        
        // 发生错误时，可以在消息列表中添加一条错误提示，或者移除刚才的乐观消息
        // 这里选择移除 AI 的临时消息，保留用户的输入以便重试
        this.messages = this.messages.filter(m => m.id !== tempAiId);
        
        throw err;
      }
    },

    /**
     * 获取分析报告列表
     */
    async fetchReports(params: { page?: number; page_size?: number; is_archived?: boolean } = {}) {
      // 报告加载通常独立于聊天，这里可以选择不共用 loading 状态，或者使用 reportsLoading
      try {
        const response = await reportApi.getReports(params);
        // 假设 response.data.items 是数组
        this.reports = response.data.items || [];
        return response;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : '获取报告列表失败';
        console.error('Fetch reports error:', err);
        // 这里不一定需要设置全局 error，视 UI 需求而定
        throw err;
      }
    }
  }
});