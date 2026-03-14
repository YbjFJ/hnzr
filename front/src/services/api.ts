import type { LoginRequest, RegisterRequest, LoginResponse, UpdateProfileRequest, UpdatePasswordRequest, User } from '../types/user';
import type { Article, Category, ArticleListResponse, ArticleResponse, CategoryListResponse } from '../types/article';
import type { ChatSessionListResponse, ChatSessionResponse, ChatMessageListResponse, AnalysisReportListResponse, AnalysisReportResponse } from '../types/chat';

// API基础URL (根据实际部署情况调整，开发环境常用 /api 走代理)
const API_BASE_URL = '/api';

// 获取当前 token：优先 localStorage，其次 Pinia 用户 store（避免 store 与 localStorage 不同步时未带 token）
async function getAuthToken(): Promise<string> {
  let token = localStorage.getItem('token') || '';
  if (!token) {
    try {
      const { useUserStore } = await import('../stores/user');
      token = useUserStore().token || '';
    } catch {
      // 避免循环依赖或 store 未挂载时报错
    }
  }
  return token;
}

// 通用请求封装 (用于普通的 JSON 响应)
const request = async <T>(url: string, options: RequestInit = {}): Promise<T> => {
  const token = await getAuthToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
  }

  return response.json() as Promise<T>;
};

// ================= 用户相关 API =================
export const userApi = {
  // 注册（公开，无需 token）
  register: (data: RegisterRequest) => request<User>('/users/register', {
    method: 'POST',
    body: JSON.stringify(data)
  }),

  // 登录
  login: (data: LoginRequest) => request<LoginResponse>('/users/login', {
    method: 'POST',
    body: JSON.stringify(data)
  }),

  // 获取当前用户信息（本人或管理员）
  getCurrentUser: (userId: number) => request<User>(`/users/${userId}`),

  // 更新个人资料（本人或管理员）
  updateProfile: (userId: number, data: UpdateProfileRequest) => request<User>(`/users/${userId}/profile`, {
    method: 'PUT',
    body: JSON.stringify(data)
  }),

  // 更新密码（仅本人）
  updatePassword: (userId: number, data: UpdatePasswordRequest) => request<User>(`/users/${userId}/password`, {
    method: 'PUT',
    body: JSON.stringify(data)
  }),

  // 忘记密码：发送验证码（15 分钟有效）
  sendForgotCode: (email: string) => request<{ message: string }>('/users/forgot-password/send-code', {
    method: 'POST',
    body: JSON.stringify({ email })
  }),
  // 忘记密码：验证码 + 新密码重置
  resetPasswordWithCode: (data: { email: string; code: string; new_password: string }) =>
    request<{ message: string }>('/users/forgot-password/reset', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  // ---------- 管理员：人员管理 ----------
  // 用户列表（仅管理员，支持 keyword）。注意用 /users/ 带斜杠，避免 307 重定向导致丢失 Authorization 头
  getUsers: (params: { skip?: number; limit?: number; keyword?: string }) => {
    const query = new URLSearchParams();
    if (params.skip != null) query.append('skip', params.skip.toString());
    if (params.limit != null) query.append('limit', params.limit.toString());
    if (params.keyword) query.append('keyword', params.keyword);
    return request<User[]>(`/users/?${query.toString()}`);
  },
  // 获取单个用户（本人或管理员）
  getUser: (userId: number) => request<User>(`/users/${userId}`),
  // 管理员创建用户
  createUser: (data: { email: string; password: string; nickname?: string; role?: string }) =>
    request<User>('/users/', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
  // 管理员更新用户（昵称、头像、角色、是否激活、新密码）
  adminUpdateUser: (userId: number, data: { nickname?: string; avatar?: string; role?: string; is_active?: boolean; new_password?: string }) =>
    request<User>(`/users/${userId}/admin`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),
  // 管理员删除用户
  deleteUser: (userId: number) =>
    request<{ message: string }>(`/users/${userId}`, {
      method: 'DELETE'
    })
};

// ================= 文章相关 API =================
export const articleApi = {
  // 获取文章列表（sort_by: date 按时间 | views 按浏览数）
  getArticles: (params: { skip?: number; limit?: number; category_id?: number; type?: string; keyword?: string; status?: string; sort_by?: string }) => {
    const query = new URLSearchParams();
    if (params.skip != null && params.skip !== undefined) query.append('skip', String(params.skip));
    if (params.limit != null && params.limit !== undefined) query.append('limit', String(params.limit));
    if (params.category_id != null && params.category_id !== undefined) query.append('category_id', String(params.category_id));
    if (params.type) query.append('type', params.type);
    if (params.keyword && params.keyword.trim()) query.append('keyword', params.keyword.trim());
    if (params.status) query.append('status', params.status);
    if (params.sort_by && (params.sort_by === 'date' || params.sort_by === 'views')) query.append('sort_by', params.sort_by);
    // 避免列表被缓存，否则切换「草稿/已发布」等时可能仍返回旧数据
    query.append('_t', String(Date.now()));
    // 使用 /articles/ 带斜杠，避免 307 重定向导致丢失 Authorization 头（与 /users/ 同理）
    return request<Article[]>('/articles/?' + query.toString());
  },
  
  // 搜索文章
  searchArticles: (keyword: string, limit?: number) => {
    const query = new URLSearchParams();
    query.append('keyword', keyword);
    if (limit) query.append('limit', limit.toString());
    
    return request<Article[]>('/articles/search?' + query.toString());
  },
  
  // 获取文章详情
  getArticle: (id: number) => request<Article>(`/articles/${id}`),
  
  // 获取分类列表
  getCategories: () => request<Category[]>('/categories'),
  
  // AI生成政策文章（非流式，保留兼容）
  generateArticle: (keyword: string, category_id: number) => {
    const query = new URLSearchParams();
    query.append('keyword', keyword);
    query.append('category_id', category_id.toString());
    
    return request<Article>(`/articles/generate?${query}`, {
      method: 'POST'
    });
  },

  /**
   * AI 流式生成政策文章：通过 onChunk 收到步骤与结果，onComplete 在流结束时调用
   */
  generateArticleStream: async (
    keyword: string,
    category_id: number,
    onChunk: (chunk: string) => void,
    onComplete: () => void
  ) => {
    const token = await getAuthToken();
    const response = await fetch(`${API_BASE_URL}/articles/generate-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: JSON.stringify({ keyword, category_id })
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');
    const decoder = new TextDecoder('utf-8');
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        onChunk(chunk);
      }
    } finally {
      reader.releaseLock();
      onComplete();
    }
  },
  
  // 发布文章
  publishArticle: (articleId: number) => request<Article>(`/articles/${articleId}/publish`, {
    method: 'PUT'
  }),
  
  // 下线文章
  offlineArticle: (articleId: number) => request<Article>(`/articles/${articleId}/offline`, {
    method: 'PUT'
  }),
  
  // 转为草稿
  draftArticle: (articleId: number) => request<Article>(`/articles/${articleId}/draft`, {
    method: 'PUT'
  }),
  
  // 更新文章
  updateArticle: (articleId: number, data: Partial<Article>) => request<Article>(`/articles/${articleId}`, {
    method: 'PUT',
    body: JSON.stringify(data)
  }),

  // 获取某篇新闻的官方解读列表
  getInterpretations: (newsId: number) => request<Article[]>(`/articles/${newsId}/interpretations`),

  // 管理员：为某篇新闻添加官方解读
  addInterpretation: (newsId: number, data: { title: string; summary?: string; content: string; category_id: number }) =>
    request<Article>(`/articles/${newsId}/interpretations`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  /**
   * 管理员：AI 流式生成解读正文
   * @param newsId 新闻 ID
   * @param onChunk 每收到一段文本的回调
   * @param onComplete 流结束时的回调
   */
  generateInterpretationStream: async (
    newsId: number,
    onChunk: (chunk: string) => void,
    onComplete: () => void
  ) => {
    const token = await getAuthToken();
    const response = await fetch(`${API_BASE_URL}/articles/${newsId}/interpretations/generate-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: JSON.stringify({})
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');
    const decoder = new TextDecoder('utf-8');
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        onChunk(chunk);
      }
    } finally {
      reader.releaseLock();
      onComplete();
    }
  }
};

// ================= 收藏相关 API =================
export const favoriteApi = {
  // 添加收藏
  addFavorite: (articleId: number) => request<{ message: string }>(`/articles/${articleId}/favorite`, {
    method: 'POST'
  }),
  
  // 取消收藏
  removeFavorite: (articleId: number) => request<{ message: string }>(`/articles/${articleId}/favorite`, {
    method: 'DELETE'
  }),
  
  // 检查是否已收藏
  checkFavorite: (articleId: number) => request<{ is_favorite: boolean }>(`/articles/${articleId}/favorite`, {
    method: 'GET'
  }),
  
  // 获取收藏列表
  getFavorites: (params: { page?: number; page_size?: number }) => request<{
    data: {
      items: Article[];
      total: number;
      page: number;
      page_size: number;
    }
  }>('/favorites/', {
    method: 'GET'
  })
};

// ================= 聊天相关 API =================
export const chatApi = {
  // 获取会话列表
  getSessions: () => request<ChatSessionListResponse>('/chats/sessions'),
  
  // 创建会话
  createSession: (title?: string) => request<ChatSessionResponse>('/chats/sessions', {
    method: 'POST',
    body: JSON.stringify({ title })
  }),
  
  // 删除会话
  deleteSession: (sessionId: string) => request<{ code: number; message: string }>(`/chats/sessions/${sessionId}`, {
    method: 'DELETE'
  }),
  
  // 更新会话标题
  updateSession: (sessionId: string, title: string) => request<ChatSessionResponse>(`/chats/sessions/${sessionId}`, {
    method: 'PUT',
    body: JSON.stringify({ title })
  }),
  
  // 获取会话消息
  getMessages: (sessionId: string) => request<ChatMessageListResponse>(`/chats/sessions/${sessionId}/messages`),
  
  // 发送消息 (旧版，非流式)
  sendMessage: (sessionId: string, content: string) => request<ChatMessageListResponse>(`/chats/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content, role: 'user' })
  }),
  
  /**
   * 发送消息 - 流式输出
   * @param sessionId 会话ID
   * @param content 消息内容
   * @param onChunk 接收到数据块时的回调
   * @param onComplete 流结束时的回调
   * @param refArticleIds 可选，用户选择的收藏文章 ID 列表，作为本条消息的知识库
   */
  sendMessageStream: async (
    sessionId: string, 
    content: string, 
    onChunk: (chunk: string) => void, 
    onComplete: () => void,
    refArticleIds?: number[]
  ) => {
    const token = await getAuthToken();
    const body: { content: string; role: string; ref_article_ids?: string } = { content, role: 'user' };
    if (refArticleIds && refArticleIds.length > 0) {
      body.ref_article_ids = refArticleIds.join(',');
    }

    const response = await fetch(`${API_BASE_URL}/chats/sessions/${sessionId}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: JSON.stringify(body)
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }
    
    const decoder = new TextDecoder('utf-8');
    
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        // { stream: true } 选项对于处理被截断的多字节字符（如中文）非常重要
        const chunk = decoder.decode(value, { stream: true });
        onChunk(chunk);
      }
    } catch (err) {
      console.error('Stream reading error:', err);
      throw err;
    } finally {
      // 释放锁并通知完成
      reader.releaseLock();
      onComplete();
    }
  }
};

// ================= 报告相关 API =================
export const reportApi = {
  // 获取报告列表
  getReports: (params: { page?: number; page_size?: number; is_archived?: boolean }) => {
    const query = new URLSearchParams();
    if (params.page) query.append('page', params.page.toString());
    if (params.page_size) query.append('page_size', params.page_size.toString());
    if (params.is_archived !== undefined) query.append('is_archived', params.is_archived.toString());
    
    return request<AnalysisReportListResponse>(`/reports?${query}`);
  },
  
  // 获取报告详情
  getReport: (id: number) => request<AnalysisReportResponse>(`/reports/${id}`),
  
  // 创建报告
  createReport: (data: { title: string; content: string; reference_article_ids: string; user_note?: string }) => request<AnalysisReportResponse>('/reports', {
    method: 'POST',
    body: JSON.stringify(data)
  }),
  
  // 更新报告
  updateReport: (id: number, data: { title?: string; user_note?: string; is_archived?: boolean }) => request<AnalysisReportResponse>(`/reports/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data)
  }),
  
  // 删除报告
  deleteReport: (id: number) => request<{ code: number; message: string }>(`/reports/${id}`, {
    method: 'DELETE'
  })
};