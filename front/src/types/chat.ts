// 聊天消息角色枚举
export enum MessageRole {
  USER = "user",
  AI = "ai"
}

// 聊天会话类型
export interface ChatSession {
  id: string;
  user_id: number;
  title: string;
  created_at: string;
}

// 聊天消息类型
export interface ChatMessage {
  id: number | string;
  session_id: string;
  role: MessageRole;
  content: string;
  ref_article_ids?: string;
  created_at: string;
}

// 咨询报告类型
export interface AnalysisReport {
  id: number;
  user_id: number;
  title: string;
  content: string;
  reference_article_ids: string;
  user_note?: string;
  is_archived: boolean;
  created_at: string;
  updated_at?: string;
}

// 响应类型
export type ChatSessionListResponse = ChatSession[];

export type ChatSessionResponse = ChatSession;

export type ChatMessageListResponse = ChatMessage[];

export interface AnalysisReportListResponse {
  data: {
    items: AnalysisReport[];
    total: number;
    page: number;
    page_size: number;
  };
}

export type AnalysisReportResponse = AnalysisReport;
