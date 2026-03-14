<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useArticleStore } from '../stores/article';
import { useUserStore } from '../stores/user';
import { articleApi } from '../services/api';
import type { Article, Category } from '../types/article';
import { ArticleStatus } from '../types/article';

const router = useRouter();
const route = useRoute();
const articleStore = useArticleStore();
const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);

const selectedCategory = ref<number | null>(null);
const selectedType = ref<string | null>(null);
const selectedStatus = ref<string | null>(null);
const currentPage = ref(1);
const searchKeyword = ref('');

// AI生成文章相关
const showGenerateModal = ref(false);
const generateKeyword = ref('');
const generateCategoryId = ref<number | null>(null);
const isGenerating = ref(false);
const generateError = ref('');
const generateStreamLog = ref('');
const generateStreamLogRef = ref<HTMLElement | null>(null);
// 展示用：去掉 [DONE]123、[ARTICLE_JSON] 等原始标记，[ERROR] 保留为错误提示
const generateStreamLogDisplay = computed(() => {
  return generateStreamLog.value
    .replace(/\[DONE\]\d+\s*/g, '')
    .replace(/\[ARTICLE_JSON\].*$/gm, '')
    .replace(/^\[ERROR\]\s*/gm, '❌ ');
});

// 解读全屏 overlay：点击「解读」时展示，需覆盖整个视口
const showInterpretationFullscreen = ref(false);

// 加载数据（支持从首页全站搜索跳转带来的 keyword 查询参数）
onMounted(async () => {
  await articleStore.fetchCategories();
  const q = route.query.keyword;
  if (typeof q === 'string' && q.trim()) {
    searchKeyword.value = q.trim();
    currentPage.value = 1;
  }
  await articleStore.fetchArticles({
    skip: (currentPage.value - 1) * 10,
    limit: 10,
    category_id: selectedCategory.value || undefined,
    type: selectedType.value || undefined,
    status: selectedStatus.value || undefined,
    keyword: searchKeyword.value || undefined
  });
});

// 切换分类
const handleCategoryChange = async (categoryId: number | null) => {
  selectedCategory.value = categoryId;
  currentPage.value = 1;
  await articleStore.fetchArticles({
    skip: 0,
    limit: 10,
    category_id: categoryId || undefined,
    type: selectedType.value || undefined,
    status: selectedStatus.value || undefined,
    keyword: searchKeyword.value || undefined
  });
};

// 切换文章类型
const handleTypeChange = async (type: string | null) => {
  selectedType.value = type;
  currentPage.value = 1;
  await articleStore.fetchArticles({
    skip: 0,
    limit: 10,
    category_id: selectedCategory.value || undefined,
    type: type || undefined,
    status: selectedStatus.value || undefined,
    keyword: searchKeyword.value || undefined
  });
  // 点击「解读」时打开全屏 overlay
  showInterpretationFullscreen.value = type === 'interpretation';
};

// 关闭解读全屏
const closeInterpretationFullscreen = () => {
  showInterpretationFullscreen.value = false;
};

// 全屏打开时禁止背景滚动
watch(showInterpretationFullscreen, (open) => {
  if (open) {
    document.body.style.overflow = 'hidden';
    document.body.style.touchAction = 'none';
  } else {
    document.body.style.overflow = '';
    document.body.style.touchAction = '';
  }
});

// 切换文章状态
const handleStatusChange = async (status: string | null) => {
  selectedStatus.value = status;
  currentPage.value = 1;
  await articleStore.fetchArticles({
    skip: 0,
    limit: 10,
    category_id: selectedCategory.value || undefined,
    type: selectedType.value || undefined,
    status: status || undefined,
    keyword: searchKeyword.value || undefined
  });
};

// 分页处理
const handlePageChange = async (page: number) => {
  currentPage.value = page;
  await articleStore.fetchArticles({
    skip: (currentPage.value - 1) * 10,
    limit: 10,
    category_id: selectedCategory.value || undefined,
    type: selectedType.value || undefined,
    status: selectedStatus.value || undefined,
    keyword: searchKeyword.value || undefined
  });
};

// 搜索文章
const handleSearch = async () => {
  currentPage.value = 1;
  await articleStore.fetchArticles({
    skip: 0,
    limit: 10,
    category_id: selectedCategory.value || undefined,
    type: selectedType.value || undefined,
    status: selectedStatus.value || undefined,
    keyword: searchKeyword.value.trim() || undefined
  });
};

// 跳转到文章详情
const goToArticle = (article: Article) => {
  console.log('点击了文章卡片', article);
  console.log('文章ID', article.id);
  router.push(`/articles/${article.id}`);
};

// 打开生成文章弹窗
const openGenerateModal = () => {
  showGenerateModal.value = true;
  generateKeyword.value = '';
  generateCategoryId.value = null;
  generateError.value = '';
  generateStreamLog.value = '';
};

// 关闭生成文章弹窗
const closeGenerateModal = () => {
  if (!isGenerating.value) {
    showGenerateModal.value = false;
    generateKeyword.value = '';
    generateCategoryId.value = null;
    generateError.value = '';
    generateStreamLog.value = '';
  }
};

// AI生成文章（流式：展示步骤与标题，完成后关闭并刷新列表）
const handleGenerateArticle = async () => {
  if (!generateKeyword.value.trim()) {
    generateError.value = '请输入关键词';
    return;
  }
  if (!generateCategoryId.value) {
    generateError.value = '请选择分类';
    return;
  }
  generateError.value = '';
  generateStreamLog.value = '';
  isGenerating.value = true;
  try {
    await articleApi.generateArticleStream(
      generateKeyword.value.trim(),
      generateCategoryId.value,
      (chunk) => {
        generateStreamLog.value += chunk;
        if (chunk.includes('[ERROR]')) {
          generateError.value = chunk.replace(/^\[ERROR\]\s*/, '').trim();
        }
        const doneMatch = chunk.match(/\[DONE\](\d+)/);
        if (doneMatch) {
          const articleIdStr = doneMatch[1];
          if (!articleIdStr) return;
          const articleId = parseInt(articleIdStr, 10);
          articleStore.fetchArticles({
            skip: 0,
            limit: 10,
            category_id: selectedCategory.value ?? undefined,
            type: selectedType.value ?? undefined,
            status: selectedStatus.value ?? undefined,
            keyword: searchKeyword.value?.trim() || undefined
          }).then(() => {
            showGenerateModal.value = false;
            generateStreamLog.value = '';
            generateKeyword.value = '';
            generateCategoryId.value = null;
            router.push(`/articles/${articleId}`);
          });
        }
        nextTick(() => {
          generateStreamLogRef.value?.scrollTo?.({ top: (generateStreamLogRef.value?.scrollHeight ?? 0), behavior: 'smooth' });
        });
      },
      () => { isGenerating.value = false; }
    );
  } catch (err) {
    generateError.value = err instanceof Error ? err.message : '生成政策文章失败';
    isGenerating.value = false;
  }
};
</script>

<template>
  <main class="home-container">
    <!-- 左侧：分类筛选、文章类型所有人可见；文章状态仅管理员可见 -->
    <div class="sidebar">
      <h3>分类筛选</h3>
      <div class="category-list">
        <div 
          class="category-item" 
          :class="{ active: selectedCategory === null }"
          @click="handleCategoryChange(null)"
        >
          全部
        </div>
        <div 
          v-for="category in articleStore.categories" 
          :key="category.id"
          class="category-item"
          :class="{ active: selectedCategory === category.id }"
          @click="handleCategoryChange(category.id)"
        >
          {{ category.name }}
        </div>
      </div>
      
      <h3>文章类型</h3>
      <div class="type-list">
        <div 
          class="type-item" 
          :class="{ active: selectedType === null }"
          @click="handleTypeChange(null)"
        >
          全部
        </div>
        <div 
          class="type-item" 
          :class="{ active: selectedType === 'news' }"
          @click="handleTypeChange('news')"
        >
          新闻
        </div>
        <div 
          class="type-item" 
          :class="{ active: selectedType === 'interpretation' }"
          @click="handleTypeChange('interpretation')"
        >
          解读
        </div>
      </div>
      
      <template v-if="isAdmin">
      <h3>文章状态</h3>
      <div class="status-list">
        <div 
          class="status-item" 
          :class="{ active: selectedStatus === null }"
          @click="handleStatusChange(null)"
        >
          全部
        </div>
        <div 
          class="status-item" 
          :class="{ active: selectedStatus === 'draft' }"
          @click="handleStatusChange('draft')"
        >
          草稿
        </div>
        <div 
          class="status-item" 
          :class="{ active: selectedStatus === 'published' }"
          @click="handleStatusChange('published')"
        >
          已发布
        </div>
        <div 
          class="status-item" 
          :class="{ active: selectedStatus === 'offline' }"
          @click="handleStatusChange('offline')"
        >
          已下线
        </div>
      </div>
      </template>
    </div>
    
    <div class="content">
      <div class="content-header">
        <button type="button" class="back-btn" @click="router.push('/')" title="返回首页">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
          返回
        </button>
        <h2>文章列表</h2>
        <div class="search-wrap">
          <input
            v-model="searchKeyword"
            type="text"
            class="search-input"
            placeholder="搜索文章标题、摘要..."
            @keyup.enter="handleSearch"
          />
          <button type="button" class="search-btn" @click="handleSearch">搜索</button>
        </div>
        <button v-if="isAdmin" class="generate-btn" @click="openGenerateModal">AI生成政策文章</button>
      </div>
      
      <div class="article-list">
        <!-- 无内容时显示友好提示 -->
        <div v-if="!articleStore.loading && articleStore.articles.length === 0" class="empty-state">
          <div class="empty-icon">📭</div>
          <p class="empty-title">当前没有内容显示</p>
          <p class="empty-desc">当前筛选条件下暂无文章，试试切换「分类」或「文章类型」</p>
        </div>
        <div 
          v-for="article in articleStore.articles" 
          :key="article.id"
          class="article-card"
        >
          <div 
            class="article-card-content"
            @click="goToArticle(article)"
          >
            <div v-if="article.cover_image" class="article-cover">
              <img :src="article.cover_image" :alt="article.title" />
            </div>
            <div class="article-info">
              <div class="article-meta">
                <span class="category">{{ article.category?.name || '未知分类' }}</span>
                <span class="type">{{ article.type === 'news' ? '新闻' : '解读' }}</span>
                <span v-if="isAdmin" :class="['status', article.status]">
                  {{ article.status === 'draft' ? '草稿' : article.status === 'published' ? '已发布' : '已下线' }}
                </span>
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
          <div v-if="isAdmin" class="article-actions">
            <button 
              v-if="article.status === 'draft'" 
              class="action-btn publish"
              @click.stop="articleStore.publishArticle(article.id)"
            >
              发布
            </button>
            <button 
              v-if="article.status === 'published'" 
              class="action-btn offline"
              @click.stop="articleStore.offlineArticle(article.id)"
            >
              下线
            </button>
            <button 
              v-if="article.status === 'offline'" 
              class="action-btn draft"
              @click.stop="articleStore.draftArticle(article.id)"
            >
              转为草稿
            </button>
            <button 
              class="action-btn edit"
              @click.stop="goToArticle(article)"
            >
              编辑
            </button>
          </div>
        </div>
      </div>
      
      <!-- 分页 -->
      <div class="pagination" v-if="articleStore.total > 10">
        <button 
          @click="handlePageChange(currentPage - 1)" 
          :disabled="currentPage === 1"
        >
          上一页
        </button>
        <span class="page-info">
          第 {{ currentPage }} 页 / 共 {{ Math.ceil(articleStore.total / 10) }} 页
        </span>
        <button 
          @click="handlePageChange(currentPage + 1)" 
          :disabled="currentPage >= Math.ceil(articleStore.total / 10)"
        >
          下一页
        </button>
      </div>
    </div>
  </main>

  <!-- AI生成文章弹窗 -->
  <div v-if="showGenerateModal" class="modal-overlay" @click="closeGenerateModal">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>AI生成政策文章</h3>
        <button class="close-btn" @click="closeGenerateModal">×</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label for="keyword">政策关键词</label>
          <input
            type="text"
            id="keyword"
            v-model="generateKeyword"
            placeholder="请输入政策关键词，如：乡村振兴 2025"
            :disabled="isGenerating"
          />
        </div>
        <div class="form-group">
          <label for="category">政策分类</label>
          <select
            id="category"
            v-model="generateCategoryId"
            :disabled="isGenerating"
          >
            <option value="">请选择分类</option>
            <option
              v-for="category in articleStore.categories"
              :key="category.id"
              :value="category.id"
            >
              {{ category.name }}
            </option>
          </select>
        </div>
        <div v-if="generateError" class="error-message">{{ generateError }}</div>
        <!-- 流式进度展示 -->
        <div v-if="generateStreamLog" class="generate-stream-box">
          <div class="generate-stream-title">生成进度</div>
          <div ref="generateStreamLogRef" class="generate-stream-log">{{ generateStreamLogDisplay }}</div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="cancel-btn" @click="closeGenerateModal" :disabled="isGenerating">取消</button>
        <button class="generate-submit-btn" @click="handleGenerateArticle" :disabled="isGenerating">
          {{ isGenerating ? '生成中...' : '生成文章' }}
        </button>
      </div>
    </div>
  </div>

  <!-- 解读全屏 overlay：挂载到 body，确保覆盖整个屏幕 -->
  <Teleport to="body">
    <div
      v-if="showInterpretationFullscreen"
      class="interpretation-fullscreen-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="解读文章"
    >
      <div class="interpretation-fullscreen-backdrop" @click="closeInterpretationFullscreen" />
      <div class="interpretation-fullscreen-content">
        <header class="interpretation-fullscreen-header">
          <h2>解读文章</h2>
          <button type="button" class="interpretation-close-btn" @click="closeInterpretationFullscreen" aria-label="关闭">×</button>
        </header>
        <div class="interpretation-fullscreen-body">
          <div v-if="!articleStore.loading && articleStore.articles.length === 0" class="empty-state interpretation-empty">
            <div class="empty-icon">📭</div>
            <p class="empty-title">当前没有内容显示</p>
            <p class="empty-desc">当前筛选条件下暂无解读文章，试试切换「分类」或关闭后选择其他类型</p>
          </div>
          <div v-else class="interpretation-article-list">
            <div
              v-for="article in articleStore.articles"
              :key="article.id"
              class="article-card"
            >
              <div class="article-card-content" @click="goToArticle(article)">
                <div v-if="article.cover_image" class="article-cover">
                  <img :src="article.cover_image" :alt="article.title" />
                </div>
                <div class="article-info">
                  <div class="article-meta">
                    <span class="category">{{ article.category?.name || '未知分类' }}</span>
                    <span class="type">解读</span>
                    <span v-if="isAdmin" :class="['status', article.status]">
                      {{ article.status === 'draft' ? '草稿' : article.status === 'published' ? '已发布' : '已下线' }}
                    </span>
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
              <div v-if="isAdmin" class="article-actions">
                <button v-if="article.status === 'draft'" class="action-btn publish" @click.stop="articleStore.publishArticle(article.id)">发布</button>
                <button v-if="article.status === 'published'" class="action-btn offline" @click.stop="articleStore.offlineArticle(article.id)">下线</button>
                <button v-if="article.status === 'offline'" class="action-btn draft" @click.stop="articleStore.draftArticle(article.id)">转为草稿</button>
                <button class="action-btn edit" @click.stop="goToArticle(article)">编辑</button>
              </div>
            </div>
          </div>
          <div class="pagination" v-if="articleStore.total > 10">
            <button @click="handlePageChange(currentPage - 1)" :disabled="currentPage === 1">上一页</button>
            <span class="page-info">第 {{ currentPage }} 页 / 共 {{ Math.ceil(articleStore.total / 10) }} 页</span>
            <button @click="handlePageChange(currentPage + 1)" :disabled="currentPage >= Math.ceil(articleStore.total / 10)">下一页</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* ========== 全局布局 ========== */
.home-container {
  display: flex;
  gap: 30px;
  padding: 30px 40px;
  max-width: 1600px;
  margin: 0 auto;
  min-height: calc(100vh - 70px);
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
}

/* ========== 侧边栏 - 现代化设计 ========== */
.sidebar {
  width: 280px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20px);
  padding: 24px;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.3);
  height: fit-content;
  position: sticky;
  top: 90px;
  animation: slideInLeft 0.6s ease-out;
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

.sidebar h3 {
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar h3::before {
  content: '';
  width: 4px;
  height: 16px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-radius: 2px;
}

.category-list,
.type-list,
.status-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 28px;
}

.category-item,
.type-item,
.status-item {
  padding: 12px 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  font-size: 14px;
  font-weight: 500;
  color: #5a5e66;
  position: relative;
  overflow: hidden;
}

.category-item::before,
.type-item::before,
.status-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 3px;
  height: 100%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  transform: scaleY(0);
  transition: transform 0.3s ease;
}

.category-item:hover,
.type-item:hover,
.status-item:hover {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08), rgba(118, 75, 162, 0.08));
  transform: translateX(5px);
  color: #667eea;
}

.category-item:hover::before,
.type-item:hover::before,
.status-item:hover::before {
  transform: scaleY(1);
}

.category-item.active,
.type-item.active,
.status-item.active {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

.category-item.active::before,
.type-item.active::before,
.status-item.active::before {
  transform: scaleY(1);
  background: rgba(255, 255, 255, 0.3);
}

/* ========== 主内容区 ========== */
.content {
  flex: 1;
  min-width: 0;
  animation: fadeIn 0.8s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.content h2 {
  margin-bottom: 24px;
  font-size: 28px;
  font-weight: 700;
  color: #2c3e50;
  letter-spacing: -0.5px;
}

/* ========== 内容头部 ========== */
.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
  padding-bottom: 20px;
  gap: 16px;
  flex-wrap: wrap;
}

.content-header .back-btn {
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

.content-header .back-btn:hover {
  background: rgba(102, 126, 234, 0.15);
  border-color: #667eea;
  color: #764ba2;
}

.content-header h2 {
  margin: 0;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* ========== 搜索栏 ========== */
.search-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  max-width: 360px;
  margin: 0 20px;
}
.search-input {
  flex: 1;
  min-width: 0;
  padding: 10px 16px;
  border: 1px solid rgba(102, 126, 234, 0.25);
  border-radius: 22px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.search-input::placeholder {
  color: #999;
}
.search-input:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.15);
}
.search-btn {
  padding: 10px 20px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
  border-radius: 22px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}
.search-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* ========== AI生成按钮 ========== */
.generate-btn {
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
  border-radius: 25px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
  display: flex;
  align-items: center;
  gap: 8px;
}

.generate-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.generate-btn:active {
  transform: translateY(0);
}

/* ========== 文章列表 ========== */
.article-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

/* ========== 无内容空状态（与文章卡片同宽） ========== */
.empty-state {
  width: 100%;
  background: white;
  border-radius: 16px;
  padding: 60px 40px;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px dashed rgba(102, 126, 234, 0.25);
  box-sizing: border-box;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.8;
}
.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: #2c3e50;
  margin: 0 0 8px 0;
}
.empty-desc {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

/* ========== 文章卡片 - 现代化设计 ========== */
.article-card {
  background: white;
  padding: 24px;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(0, 0, 0, 0.06);
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  position: relative;
  overflow: hidden;
}

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
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(102, 126, 234, 0.2);
}

.article-card:hover::before {
  opacity: 1;
}

.article-card-content {
  display: flex;
  gap: 24px;
  cursor: pointer;
  margin-bottom: 16px;
}

.article-cover {
  width: 240px;
  height: 150px;
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
  font-size: 12px;
  flex-wrap: wrap;
}

.category {
  background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
  color: #667eea;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 600;
}

.type {
  background: linear-gradient(135deg, #d1fae5, #a7f3d0);
  color: #059669;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 600;
}

.status {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.status.draft {
  background: linear-gradient(135deg, #fee2e2, #fecaca);
  color: #dc2626;
}

.status.published {
  background: linear-gradient(135deg, #d1fae5, #a7f3d0);
  color: #059669;
}

.status.offline {
  background: linear-gradient(135deg, #f3f4f6, #e5e7eb);
  color: #6b7280;
}

.date {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #d97706;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 600;
  margin-left: auto;
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
}

.article-footer {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #9ca3af;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}

/* ========== 文章操作按钮 ========== */
.article-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f2f5;
}

.action-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.action-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.action-btn.publish {
  background: linear-gradient(135deg, #059669, #10b981);
  color: white;
}

.action-btn.publish:hover {
  box-shadow: 0 4px 15px rgba(5, 150, 105, 0.3);
}

.action-btn.offline {
  background: linear-gradient(135deg, #dc2626, #ef4444);
  color: white;
}

.action-btn.offline:hover {
  box-shadow: 0 4px 15px rgba(220, 38, 38, 0.3);
}

.action-btn.draft {
  background: linear-gradient(135deg, #d97706, #f59e0b);
  color: white;
}

.action-btn.draft:hover {
  box-shadow: 0 4px 15px rgba(217, 119, 6, 0.3);
}

.action-btn.edit {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
}

.action-btn.edit:hover {
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
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

/* ========== 解读全屏 overlay（覆盖整个屏幕） ========== */
.interpretation-fullscreen-overlay {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  display: flex;
  align-items: stretch;
  justify-content: center;
  animation: fadeIn 0.25s ease;
}
.interpretation-fullscreen-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(6px);
}
.interpretation-fullscreen-content {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 900px;
  margin: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 48px);
  overflow: hidden;
}
.interpretation-fullscreen-header {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: rgba(255, 255, 255, 0.95);
  border-bottom: 2px solid rgba(102, 126, 234, 0.15);
  border-radius: 20px 20px 0 0;
}
.interpretation-fullscreen-header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #2c3e50;
}
.interpretation-close-btn {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.06);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  color: #5a5e66;
  transition: all 0.25s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}
.interpretation-close-btn:hover {
  background: rgba(220, 38, 38, 0.12);
  color: #dc2626;
  transform: rotate(90deg);
}
.interpretation-fullscreen-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.interpretation-article-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.interpretation-fullscreen-body .pagination {
  margin-top: 24px;
  justify-content: center;
}
.interpretation-empty {
  margin: 0;
}

/* ========== 弹窗样式 ========== */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  animation: fadeIn 0.3s ease;
}

.modal-content {
  background: white;
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  width: 90%;
  max-width: 520px;
  max-height: 80vh;
  overflow: hidden;
  animation: slideInUp 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 28px;
  border-bottom: 2px solid rgba(102, 126, 234, 0.1);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
}

.modal-header h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #2c3e50;
}

.close-btn {
  background: rgba(0, 0, 0, 0.05);
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 20px;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
  transform: rotate(90deg);
}

.modal-body {
  padding: 28px;
}

.form-group {
  margin-bottom: 24px;
}

.form-group label {
  display: block;
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  font-size: 14px;
  color: #374151;
  transition: all 0.3s ease;
  background: #f9fafb;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #667eea;
  background: white;
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
}

.form-group input:disabled,
.form-group select:disabled {
  background: #f3f4f6;
  cursor: not-allowed;
  opacity: 0.6;
}

.error-message {
  color: #dc2626;
  font-size: 13px;
  margin-top: 8px;
  padding: 10px 14px;
  background: rgba(220, 38, 38, 0.1);
  border-radius: 8px;
  font-weight: 500;
}

.generate-stream-box {
  margin-top: 16px;
  padding: 14px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.06), rgba(118, 75, 162, 0.06));
  border: 1px solid rgba(102, 126, 234, 0.2);
  border-radius: 12px;
}

.generate-stream-title {
  font-size: 13px;
  color: #667eea;
  margin-bottom: 8px;
  font-weight: 600;
}

.generate-stream-log {
  max-height: 200px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding: 20px 28px;
  border-top: 2px solid rgba(102, 126, 234, 0.1);
  background: #f9fafb;
}

.cancel-btn {
  padding: 10px 20px;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  color: #5a5e66;
  cursor: pointer;
  transition: all 0.3s ease;
}

.cancel-btn:hover {
  border-color: #667eea;
  color: #667eea;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}

.cancel-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.generate-submit-btn {
  padding: 10px 24px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.generate-submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.generate-submit-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

/* ========== 响应式设计（仅小屏/平板竖排，电脑端保持左右分栏） ========== */
@media (max-width: 768px) {
  .home-container {
    flex-direction: column;
    padding: 20px;
  }

  .sidebar {
    width: 100%;
    position: static;
  }

  .article-card-content {
    flex-direction: column;
  }

  .article-cover {
    width: 100%;
    height: 200px;
  }

  .content-header {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }
  .search-wrap {
    max-width: none;
    margin: 0;
  }

  .article-actions {
    flex-wrap: wrap;
  }
}
</style>