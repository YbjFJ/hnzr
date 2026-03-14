import { defineStore } from 'pinia';
import type { Article, Category } from '../types/article';
import { articleApi } from '../services/api';

export const useArticleStore = defineStore('article', {
  state: () => ({
    articles: [] as Article[],
    categories: [] as Category[],
    currentArticle: null as Article | null,
    total: 0,
    page: 1,
    pageSize: 10,
    loading: false,
    error: null as string | null
  }),

  getters: {
    paginatedArticles: (state) => state.articles
  },

  actions: {
    // 获取文章列表（sort_by: date 按时间 | views 按浏览数，用于首页最新推荐等）
    async fetchArticles(params: { skip?: number; limit?: number; category_id?: number; type?: string; keyword?: string; status?: string; sort_by?: string }) {
      this.loading = true;
      this.error = null;
      try {
        const articles = await articleApi.getArticles({
          skip: params.skip || 0,
          limit: params.limit || this.pageSize,
          category_id: params.category_id,
          type: params.type,
          keyword: params.keyword,
          status: params.status,
          sort_by: params.sort_by
        });
        this.articles = articles;
        this.total = articles.length;
        return articles;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '获取文章列表失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    // 搜索文章
    async searchArticles(keyword: string, limit?: number) {
      this.loading = true;
      this.error = null;
      try {
        const articles = await articleApi.searchArticles(keyword, limit);
        this.articles = articles;
        this.total = articles.length;
        return articles;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '搜索文章失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    // 获取文章详情
    async fetchArticle(id: number) {
      this.loading = true;
      this.error = null;
      try {
        const article = await articleApi.getArticle(id);
        this.currentArticle = article;
        return article;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '获取文章详情失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    // 获取分类列表
    async fetchCategories() {
      if (this.categories.length > 0) return;
      
      this.loading = true;
      this.error = null;
      try {
        const categories = await articleApi.getCategories();
        this.categories = categories;
        return categories;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '获取分类列表失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    // AI生成政策文章
    async generateArticle(keyword: string, category_id: number) {
      this.loading = true;
      this.error = null;
      try {
        const article = await articleApi.generateArticle(keyword, category_id);
        // 将生成的文章添加到列表开头
        this.articles.unshift(article);
        this.total += 1;
        return article;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '生成政策文章失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },

    // 重置当前文章
    resetCurrentArticle() {
      this.currentArticle = null;
    },
    
    // 发布文章
    async publishArticle(articleId: number) {
      this.loading = true;
      this.error = null;
      try {
        const updatedArticle = await articleApi.publishArticle(articleId);
        // 更新本地文章列表中的文章
        const index = this.articles.findIndex(article => article.id === articleId);
        if (index !== -1) {
          this.articles[index] = updatedArticle;
        }
        // 更新当前文章（如果正在查看这篇文章）
        if (this.currentArticle && this.currentArticle.id === articleId) {
          this.currentArticle = updatedArticle;
        }
        return updatedArticle;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '发布文章失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },
    
    // 下线文章
    async offlineArticle(articleId: number) {
      this.loading = true;
      this.error = null;
      try {
        const updatedArticle = await articleApi.offlineArticle(articleId);
        // 更新本地文章列表中的文章
        const index = this.articles.findIndex(article => article.id === articleId);
        if (index !== -1) {
          this.articles[index] = updatedArticle;
        }
        // 更新当前文章（如果正在查看这篇文章）
        if (this.currentArticle && this.currentArticle.id === articleId) {
          this.currentArticle = updatedArticle;
        }
        return updatedArticle;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '下线文章失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },
    
    // 转为草稿
    async draftArticle(articleId: number) {
      this.loading = true;
      this.error = null;
      try {
        const updatedArticle = await articleApi.draftArticle(articleId);
        // 更新本地文章列表中的文章
        const index = this.articles.findIndex(article => article.id === articleId);
        if (index !== -1) {
          this.articles[index] = updatedArticle;
        }
        // 更新当前文章（如果正在查看这篇文章）
        if (this.currentArticle && this.currentArticle.id === articleId) {
          this.currentArticle = updatedArticle;
        }
        return updatedArticle;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '转为草稿失败';
        throw err;
      } finally {
        this.loading = false;
      }
    },
    
    // 更新文章
    async updateArticle(articleId: number, data: Partial<Article>) {
      this.loading = true;
      this.error = null;
      try {
        const updatedArticle = await articleApi.updateArticle(articleId, data);
        // 更新本地文章列表中的文章
        const index = this.articles.findIndex(article => article.id === articleId);
        if (index !== -1) {
          this.articles[index] = updatedArticle;
        }
        // 更新当前文章（如果正在查看这篇文章）
        if (this.currentArticle && this.currentArticle.id === articleId) {
          this.currentArticle = updatedArticle;
        }
        return updatedArticle;
      } catch (err) {
        this.error = err instanceof Error ? err.message : '更新文章失败';
        throw err;
      } finally {
        this.loading = false;
      }
    }
  }
});
