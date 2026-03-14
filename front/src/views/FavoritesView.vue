<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { favoriteApi } from '../services/api';
import type { Article } from '../types/article';
import { useUserStore } from '../stores/user';

const router = useRouter();
const userStore = useUserStore();

const favorites = ref<Article[]>([]);
const loading = ref(false);
const error = ref('');
const currentPage = ref(1);
const total = ref(0);
const pageSize = ref(10);

// 加载收藏列表
onMounted(async () => {
  // 检查用户是否登录
  if (!userStore.isLoggedIn) {
    router.push('/login');
    return;
  }
  await fetchFavorites();
});

// 获取收藏列表
const fetchFavorites = async () => {
  loading.value = true;
  try {
    const response = await favoriteApi.getFavorites({
      page: currentPage.value,
      page_size: pageSize.value
    });
    favorites.value = response.data.items;
    total.value = response.data.total;
    currentPage.value = response.data.page;
    pageSize.value = response.data.page_size;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取收藏列表失败';
    console.error('获取收藏列表失败:', err);
    // 检查是否是未授权错误
    if (err instanceof Error && err.message.includes('401')) {
      userStore.logout();
      router.push('/login');
    }
  } finally {
    loading.value = false;
  }
};

// 取消收藏
const removeFavorite = async (articleId: number) => {
  try {
    await favoriteApi.removeFavorite(articleId);
    // 重新加载收藏列表
    await fetchFavorites();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '取消收藏失败';
    console.error('取消收藏失败:', err);
    // 3秒后清除错误信息
    setTimeout(() => {
      error.value = '';
    }, 3000);
  }
};

// 跳转到文章详情
const goToArticle = (article: Article) => {
  router.push(`/articles/${article.id}`);
};

// 分页处理
const handlePageChange = async (page: number) => {
  currentPage.value = page;
  await fetchFavorites();
};

// 返回上一页或首页
const goBack = () => {
  if (window.history.length > 1) {
    router.back();
  } else {
    router.push('/');
  }
};
</script>

<template>
  <div class="favorites-container">
    <div class="page-header">
      <button type="button" class="back-btn" @click="goBack" title="返回">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
        返回
      </button>
      <h2>我的收藏</h2>
    </div>
    
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
    
    <div v-if="loading" class="loading">
      加载中...
    </div>
    
    <div v-else-if="favorites.length === 0" class="empty-favorites">
      <h3>暂无收藏</h3>
      <p>您还没有收藏任何文章</p>
      <button class="go-to-articles" @click="router.push('/')">
        去浏览文章
      </button>
    </div>
    
    <div v-else class="articles-list">
      <div 
        v-for="article in favorites" 
        :key="article.id"
        class="article-card"
      >
        <div class="article-content" @click="goToArticle(article)">
          <div v-if="article.cover_image" class="article-cover">
            <img :src="article.cover_image" :alt="article.title" />
          </div>
          <div class="article-info">
            <div class="article-meta">
              <span class="category">{{ article.category?.name || '未知分类' }}</span>
              <span class="type">{{ article.type === 'news' ? '新闻' : '解读' }}</span>
              <span class="date">{{ new Date(article.publish_date).toLocaleDateString() }}</span>
            </div>
            <h3 class="article-title">{{ article.title }}</h3>
            <p class="article-summary" v-if="article.summary">{{ article.summary }}</p>
            <div class="article-footer">
              <span class="source">{{ article.source_name }}</span>
              <span class="views">{{ article.view_count }} 阅读</span>
            </div>
          </div>
        </div>
        
        <button 
          class="remove-btn"
          @click.stop="removeFavorite(article.id)"
          :disabled="loading"
        >
          取消收藏
        </button>
      </div>
    </div>
    
    <!-- 分页 -->
    <div class="pagination" v-if="total > pageSize">
      <button 
        @click="handlePageChange(currentPage - 1)" 
        :disabled="currentPage === 1"
      >
        上一页
      </button>
      <span class="page-info">
        第 {{ currentPage }} 页 / 共 {{ Math.ceil(total / pageSize) }} 页
      </span>
      <button 
        @click="handlePageChange(currentPage + 1)" 
        :disabled="currentPage >= Math.ceil(total / pageSize)"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<style scoped>
/* ========== 全局布局 ========== */
.favorites-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 30px 40px;
  min-height: calc(100vh - 70px);
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
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

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 30px;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-size: 14px;
  color: #667eea;
  background: rgba(102, 126, 234, 0.08);
  border: 1px solid rgba(102, 126, 234, 0.25);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-weight: 500;
  flex-shrink: 0;
}

.back-btn:hover {
  background: rgba(102, 126, 234, 0.15);
  border-color: #667eea;
  color: #764ba2;
}

.favorites-container .page-header h2 {
  margin: 0;
  font-size: 32px;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.5px;
}

/* ========== 错误提示 ========== */
.error-message {
  background: linear-gradient(135deg, rgba(220, 38, 38, 0.1), rgba(239, 68, 68, 0.1));
  color: #dc2626;
  padding: 14px 20px;
  border-radius: 12px;
  margin-bottom: 24px;
  font-size: 14px;
  font-weight: 600;
  border-left: 4px solid #dc2626;
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.1);
  animation: slideInDown 0.4s ease-out;
}

@keyframes slideInDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ========== 加载状态 ========== */
.loading {
  text-align: center;
  padding: 80px 0;
  color: #6b7280;
  font-size: 16px;
  font-weight: 500;
}

.loading::before {
  content: '';
  display: inline-block;
  width: 40px;
  height: 40px;
  border: 4px solid rgba(102, 126, 234, 0.1);
  border-top: 4px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ========== 空状态 ========== */
.empty-favorites {
  text-align: center;
  padding: 80px 40px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 2px solid rgba(102, 126, 234, 0.1);
  animation: fadeInUp 0.6s ease-out;
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

.empty-favorites h3 {
  margin: 0 0 12px 0;
  font-size: 24px;
  color: #2c3e50;
  font-weight: 700;
}

.empty-favorites p {
  color: #6b7280;
  font-size: 16px;
  margin-bottom: 24px;
}

.go-to-articles {
  padding: 12px 28px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
  border-radius: 25px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.go-to-articles:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

/* ========== 文章列表 ========== */
.articles-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 40px;
}

/* ========== 文章卡片 ========== */
.article-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  overflow: hidden;
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  position: relative;
  border: 1px solid rgba(0, 0, 0, 0.06);
  animation: fadeInUp 0.6s ease-out backwards;
}

.article-card:nth-child(1) { animation-delay: 0.1s; }
.article-card:nth-child(2) { animation-delay: 0.2s; }
.article-card:nth-child(3) { animation-delay: 0.3s; }
.article-card:nth-child(4) { animation-delay: 0.4s; }
.article-card:nth-child(5) { animation-delay: 0.5s; }

.article-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #667eea, #764ba2);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.article-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 12px 40px rgba(102, 126, 234, 0.2);
}

.article-card:hover::before {
  opacity: 1;
}

.article-content {
  display: flex;
  gap: 24px;
  padding: 24px;
  cursor: pointer;
}

.article-cover {
  width: 240px;
  height: 160px;
  flex-shrink: 0;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.article-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s ease;
}

.article-card:hover .article-cover img {
  transform: scale(1.1);
}

.article-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.article-meta {
  display: flex;
  gap: 10px;
  font-size: 13px;
  flex-wrap: wrap;
}

.category {
  background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
  color: #667eea;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.15);
}

.type {
  background: linear-gradient(135deg, #d1fae5, #a7f3d0);
  color: #059669;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(5, 150, 105, 0.15);
}

.date {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #d97706;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(217, 119, 6, 0.15);
}

.article-title {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0;
  line-height: 1.4;
  transition: color 0.3s ease;
}

.article-card:hover .article-title {
  color: #667eea;
}

.article-summary {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.article-footer {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #9ca3af;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
  font-weight: 500;
}

/* ========== 取消收藏按钮 ========== */
.remove-btn {
  position: absolute;
  top: 20px;
  right: 20px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #dc2626, #ef4444);
  color: white;
  border: none;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  z-index: 1;
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.3);
}

.remove-btn:hover:not(:disabled) {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 6px 16px rgba(220, 38, 38, 0.4);
}

.remove-btn:disabled {
  background: linear-gradient(135deg, #fca5a5, #f87171);
  cursor: not-allowed;
  opacity: 0.6;
}

/* ========== 分页 ========== */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  margin-top: 40px;
  padding: 20px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
}

.pagination button {
  padding: 10px 20px;
  border: 2px solid #e5e7eb;
  background: white;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #5a5e66;
}

.pagination button:hover:not(:disabled) {
  border-color: #667eea;
  color: #667eea;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
}

.pagination button:disabled {
  background: #f3f4f6;
  border-color: #e5e7eb;
  cursor: not-allowed;
  opacity: 0.5;
}

.page-info {
  font-size: 14px;
  font-weight: 600;
  color: #5a5e66;
  padding: 0 10px;
}

/* ========== 响应式设计 ========== */
@media (max-width: 768px) {
  .favorites-container {
    padding: 20px;
  }

  .favorites-container h2 {
    font-size: 24px;
  }

  .article-content {
    flex-direction: column;
  }

  .article-cover {
    width: 100%;
    height: 200px;
  }

  .pagination {
    flex-wrap: wrap;
  }
}
</style>