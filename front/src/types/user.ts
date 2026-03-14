// 用户角色枚举
export enum UserRole {
  USER = "user",
  ADMIN = "admin"
}

// 用户类型
export interface User {
  id: number;
  email: string;
  nickname?: string;
  avatar?: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// 登录请求类型
export interface LoginRequest {
  email: string;
  password: string;
}

// 登录响应类型
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  email: string;
  nickname?: string;
  role: string;
}

// 注册请求类型
export interface RegisterRequest {
  email: string;
  password: string;
  nickname?: string;
  role?: UserRole;
}

// 更新个人资料请求类型
export interface UpdateProfileRequest {
  nickname?: string;
  avatar?: string;
}

// 更新密码请求类型
export interface UpdatePasswordRequest {
  old_password: string;
  new_password: string;
}

// 通用响应类型
export interface ApiResponse<T> {
  code?: number;
  message?: string;
  data: T;
}
