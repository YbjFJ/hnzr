import { defineStore } from 'pinia';
import type { User } from '../types/user';
import { userApi } from '../services/api';

export const useUserStore = defineStore('user', {
  state: () => {
    const stored = localStorage.getItem('user');
    const user = stored ? (JSON.parse(stored) as User) : null;
    return {
      user,
      token: localStorage.getItem('token') || '',
      loading: false,
      error: null as string | null
    };
  },

  getters: {
    isLoggedIn: (state) => !!state.token,
    isAdmin: (state) => state.user?.role === 'admin'
  },

  actions: {
    // 登录
    async login(email: string, password: string) {
      this.loading = true;
      this.error = null;
      try {
        const response = await userApi.login({ email, password });
        // 登录成功后直接返回token和用户信息
        this.token = response.access_token;
        // 构建用户对象
        this.user = {
          id: response.user_id,
          email: response.email,
          nickname: response.nickname,
          role: response.role as any,
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        };
        localStorage.setItem('token', this.token);
        localStorage.setItem('user', JSON.stringify(this.user));
        return response;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '登录失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    // 注册
    async register(email: string, password: string, nickname?: string) {
      this.loading = true;
      this.error = null;
      try {
        const user = await userApi.register({ email, password, nickname });
        // 注册成功后需要手动登录
        await this.login(email, password);
        return user;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '注册失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    // 获取当前用户信息
    async fetchCurrentUser() {
      if (!this.token || !this.user?.id) return;
      
      this.loading = true;
      this.error = null;
      try {
        const user = await userApi.getCurrentUser(this.user.id);
        this.user = user;
        localStorage.setItem('user', JSON.stringify(user));
      } catch (err) {
        this.error = err instanceof Error ? err.message : '获取用户信息失败';
        // 如果获取失败，清除token
        this.logout();
      } finally {
        this.loading = false;
      }
    },

    // 更新个人资料
    async updateProfile(data: { nickname?: string; avatar?: string }) {
      if (!this.token || !this.user?.id) throw new Error('请先登录');
      
      this.loading = true;
      this.error = null;
      try {
        const updatedUser = await userApi.updateProfile(this.user.id, data);
        this.user = updatedUser;
        localStorage.setItem('user', JSON.stringify(this.user));
        return updatedUser;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '更新个人资料失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    // 修改密码
    async updatePassword(data: { old_password: string; new_password: string }) {
      if (!this.token || !this.user?.id) throw new Error('请先登录');
      
      this.loading = true;
      this.error = null;
      try {
        const updatedUser = await userApi.updatePassword(this.user.id, data);
        return updatedUser;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '修改密码失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    // 登出
    logout() {
      this.user = null;
      this.token = '';
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
  }
});
