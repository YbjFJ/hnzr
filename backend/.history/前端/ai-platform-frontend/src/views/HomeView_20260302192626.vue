<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '../stores/user';
import { useArticleStore } from '../stores/article';
import { 
  ChatLineRound, Star, SwitchButton, 
  CaretBottom, Message, Search, DataLine, Document, UserFilled
} from '@element-plus/icons-vue';

const router = useRouter();
const userStore = useUserStore();
const articleStore = useArticleStore();

const userInfo = computed(() => {
  const user = userStore.user as import('../types/user').User || {
    email: '',
    nickname: '',
    avatar: ''
  };
  return {
    isLoggedIn: !!userStore.token,
    nickname: user.nickname || user.email?.split('@')[0] || '游客',
    userPic: user.avatar || 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png',
  };
});

onMounted(async () => {
  await Promise.all([
    articleStore.fetchCategories(),
    // 最新推荐：仅展示已上线内容，按浏览数排序
    articleStore.fetchArticles({ skip: 0, limit: 20, sort_by: 'views', status: 'published' })
  ]);
});

const handleCommand = (cmd: string) => {
  if (cmd === 'logout') { userStore.logout(); router.push('/login'); }
  else if (cmd === 'chat') router.push('/chat');
  else if (cmd === 'profile') router.push('/profile');
  else if (cmd === 'adminUsers') router.push('/admin/users');
};

// 全站搜索：跳转到文章列表并带上关键词
const globalSearchKeyword = ref('');
const goToSearch = () => {
  const kw = globalSearchKeyword.value?.trim();
  if (kw) {
    router.push({ path: '/articles', query: { keyword: kw } });
  } else {
    router.push('/articles');
  }
};
</script>

<template>
  <div class="home-layout">
    <!-- 顶部导航 -->
    <header class="navbar">
      <div class="navbar-content">
        <div class="left-section">
          <div class="logo-area" @click="router.push('/')">
            <div class="logo-box">G</div>
            <span class="logo-text">格智学舟</span>
          </div>
          
          <nav class="nav-links">
            <a class="active">首页</a>
            <a @click="router.push('/articles')">文章</a>
            <a @click="router.push('/chat')">AI 咨询</a>
            <a v-if="userStore.isAdmin" @click="router.push('/admin/users')">用户管理</a>
          </nav>
        </div>

        <div class="right-area">
          <el-input
            v-model="globalSearchKeyword"
            prefix-icon="Search"
            placeholder="全站搜索..."
            class="search-input"
            clearable
            @keyup.enter="goToSearch"
          >
            <template #suffix>
              <el-icon class="search-go-icon" @click="goToSearch"><Search /></el-icon>
            </template>
          </el-input>
          
          <div v-if="userInfo.isLoggedIn" class="user-profile">
            <el-dropdown @command="handleCommand">
              <div class="avatar-wrap">
                <el-avatar :size="32" :src="userInfo.userPic" />
                <span class="name">{{ userInfo.nickname }}</span>
                <el-icon><CaretBottom /></el-icon>
              </div>
              <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile" :icon="Document">个人中心</el-dropdown-item>
                <el-dropdown-item v-if="userStore.isAdmin" command="adminUsers" :icon="UserFilled">用户管理</el-dropdown-item>
                <el-dropdown-item command="logout" :icon="SwitchButton">退出</el-dropdown-item>
              </el-dropdown-menu>
            </template>
            </el-dropdown>
          </div>
          <el-button v-else type="primary" round @click="router.push('/login')">登录</el-button>
        </div>
      </div>
    </header>

    <!-- 主内容 -->
    <main class="main-wrapper">
      <!-- 顶部 Banner -->
      <div class="hero-banner">
        <div class="hero-content">
          <h1>AI 智能资讯与咨询平台</h1>
          <p>聚合前沿科技，连接未来智慧。您的专属 AI 助手已就绪。</p>
          <el-button type="primary" size="large" class="hero-btn" @click="router.push('/chat')">
            立即开始咨询 <el-icon class="el-icon--right"><ChatLineRound /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- 内容区 -->
      <div class="content-grid">
        <!-- 左侧文章流：flex: 1 自动撑满剩余宽度 -->
        <div class="feed-section">
          <div class="section-title">
            <h3><el-icon><DataLine /></el-icon> 最新推荐</h3>
            <div class="tags">
              <span class="tag active">全部</span>
              <span class="tag">科技</span>
              <span class="tag">AI</span>
            </div>
          </div>

          <!-- 文章列表：使用 auto-fit 自动填充列 -->
          <div class="article-list">
            <div 
              v-for="article in articleStore.articles" 
              :key="article.id" 
              class="article-card"
              @click="router.push(`/articles/${article.id}`)"
            >
              <div class="card-cover">
                <img v-if="article.cover_image" :src="article.cover_image" />
                <div v-else class="placeholder">GZ</div>
              </div>
              <div class="card-info">
                <h4>{{ article.title }}</h4>
                <p>{{ article.summary }}</p>
                <div class="meta">
                  <span>{{ article.source_name }}</span>
                  <span>{{ new Date(article.publish_date).toLocaleDateString() }}</span>
                </div>
              </div>
            </div>
             <!-- 这里的空状态用于演示，如果没有数据 -->
             <el-empty v-if="articleStore.articles.length === 0" description="暂无内容" />
          </div>
        </div>

        <!-- 右侧边栏：固定宽度 -->
        <aside class="sidebar">
          <div class="widget user-widget">
            <div class="widget-bg"></div>
            <div class="widget-body">
              <el-avatar :size="64" :src="userInfo.userPic" class="widget-avatar" />
              <h3>{{ userInfo.nickname }}</h3>
              <p>欢迎来到格智学舟</p>
            </div>
          </div>

          <div class="widget nav-widget">
            <div class="menu-item" @click="router.push('/chat')">
              <el-icon class="icon blue"><ChatLineRound /></el-icon>
              <span>AI 对话助手</span>
            </div>
            <div class="menu-item" @click="router.push('/articles')">
              <el-icon class="icon purple"><Document /></el-icon>
              <span>行业政策新闻与解读</span>
            </div>
            <div class="menu-item" @click="router.push('/favorites')">
              <el-icon class="icon yellow"><Star /></el-icon>
              <span>我的收藏</span>
            </div>
          </div>
        </aside>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ========== 全局布局 ========== */
.home-layout {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  display: flex;
  flex-direction: column;
}

/* ========== 导航栏 - 毛玻璃效果 ========== */
.navbar {
  width: 100%;
  height: 70px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.08);
  position: sticky;
  top: 0;
  z-index: 999;
  border-bottom: 1px solid rgba(255, 255, 255, 0.3);
}

.navbar-content {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 40px;
  box-sizing: border-box;
  animation: slideDown 0.6s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.left-section {
  display: flex;
  align-items: center;
  gap: 60px;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 700;
  font-size: 22px;
  cursor: pointer;
  transition: transform 0.3s ease;
}

.logo-area:hover {
  transform: scale(1.05);
}

.logo-box {
  width: 38px;
  height: 38px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

.nav-links {
  display: flex;
  gap: 36px;
}

.nav-links a {
  font-size: 16px;
  color: #5a5e66;
  cursor: pointer;
  font-weight: 500;
  position: relative;
  padding: 8px 0;
  transition: color 0.3s ease;
}

.nav-links a::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  width: 0;
  height: 2px;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.3s ease;
  border-radius: 2px;
}

.nav-links a:hover,
.nav-links a.active {
  color: #667eea;
}

.nav-links a:hover::after,
.nav-links a.active::after {
  width: 100%;
}

.right-area {
  display: flex;
  align-items: center;
  gap: 20px;
}

.search-input {
  width: 260px;
  animation: fadeIn 0.8s ease-out 0.2s backwards;
}

.search-go-icon {
  cursor: pointer;
  padding: 0 4px;
}
.search-go-icon:hover {
  color: #667eea;
}

.search-input :deep(.el-input__wrapper) {
  border-radius: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}

.search-input :deep(.el-input__wrapper:hover) {
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.15);
}

.avatar-wrap {
  display: flex;
  align-items: center;
  cursor: pointer;
  gap: 10px;
  font-size: 14px;
  padding: 6px 12px;
  border-radius: 20px;
  transition: all 0.3s ease;
}

.avatar-wrap:hover {
  background: rgba(102, 126, 234, 0.08);
}

/* ========== 主体内容容器 ========== */
.main-wrapper {
  width: 100%;
  flex: 1;
  padding: 30px 40px;
  box-sizing: border-box;
}

/* ========== Hero Banner - 动态渐变背景 ========== */
.hero-banner {
  height: 320px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  background-size: 200% 200%;
  border-radius: 20px;
  display: flex;
  align-items: center;
  padding: 0 70px;
  color: white;
  margin-bottom: 40px;
  box-shadow: 0 20px 60px rgba(102, 126, 234, 0.35);
  position: relative;
  overflow: hidden;
  animation: gradientShift 8s ease infinite, fadeInUp 0.8s ease-out;
}

@keyframes gradientShift {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.hero-banner::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: url('data:image/svg+xml,<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><defs><pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1"/></pattern></defs><rect width="100" height="100" fill="url(%23grid)"/></svg>');
  opacity: 0.5;
}

.hero-banner::after {
  content: '';
  position: absolute;
  top: -50%;
  right: -10%;
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
  border-radius: 50%;
  animation: float 6s ease-in-out infinite;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-20px);
  }
}

.hero-content {
  position: relative;
  z-index: 1;
}

.hero-content h1 {
  font-size: 42px;
  margin-bottom: 16px;
  font-weight: 700;
  text-shadow: 0 2px 20px rgba(0, 0, 0, 0.15);
  letter-spacing: -0.5px;
}

.hero-content p {
  font-size: 18px;
  opacity: 0.95;
  margin-bottom: 30px;
  font-weight: 300;
  letter-spacing: 0.5px;
}

.hero-btn {
  padding: 14px 36px;
  font-size: 16px;
  border-radius: 25px;
  background: white;
  color: #667eea;
  font-weight: 600;
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
  transition: all 0.3s ease;
  animation: pulse 2s ease-in-out infinite;
}

.hero-btn:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.3);
  animation: none;
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
  }
  50% {
    box-shadow: 0 8px 35px rgba(255, 255, 255, 0.3);
  }
}

/* ========== 内容网格布局 ========== */
.content-grid {
  display: flex;
  gap: 35px;
  align-items: flex-start;
  animation: fadeIn 0.8s ease-out 0.4s backwards;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.feed-section {
  flex: 1;
  min-width: 0;
}

.sidebar {
  width: 340px;
  flex-shrink: 0;
  animation: slideInRight 0.8s ease-out 0.6s backwards;
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* ========== 区域标题 ========== */
.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-title h3 {
  font-size: 20px;
  font-weight: 600;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title .el-icon {
  color: #667eea;
  font-size: 22px;
}

.tags .tag {
  padding: 6px 16px;
  background: white;
  border-radius: 18px;
  margin-left: 10px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  font-weight: 500;
}

.tags .tag:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
}

.tags .tag.active {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

/* ========== 文章列表 - 现代化卡片设计 ========== */
.article-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}

.article-card {
  background: white;
  border-radius: 16px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid rgba(0, 0, 0, 0.06);
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  position: relative;
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
  transform: translateY(-8px) scale(1.02);
  box-shadow: 0 15px 40px rgba(102, 126, 234, 0.2);
}

.article-card:hover::before {
  opacity: 1;
}

.card-cover {
  height: 180px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  position: relative;
  overflow: hidden;
}

.card-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s ease;
}

.article-card:hover .card-cover img {
  transform: scale(1.1);
}

.placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  font-weight: 700;
  color: rgba(102, 126, 234, 0.3);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
}

.card-info {
  padding: 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
}

.card-info h4 {
  margin: 0 0 10px;
  font-size: 17px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-weight: 600;
  color: #2c3e50;
  transition: color 0.3s ease;
}

.article-card:hover .card-info h4 {
  color: #667eea;
}

.card-info p {
  font-size: 14px;
  color: #7f8c8d;
  margin-bottom: 14px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
  line-height: 1.6;
}

.meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #95a5a6;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}

/* ========== 侧边栏组件 - 美化设计 ========== */
.widget {
  background: white;
  border-radius: 16px;
  margin-bottom: 24px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}

.widget:hover {
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
}

.widget-bg {
  height: 100px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  position: relative;
  overflow: hidden;
}

.widget-bg::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
  animation: rotate 20s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.widget-body {
  text-align: center;
  margin-top: -45px;
  padding-bottom: 28px;
  position: relative;
  z-index: 1;
}

.widget-avatar {
  border: 5px solid white;
  background: white;
  margin-bottom: 12px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.widget-body h3 {
  font-size: 20px;
  font-weight: 600;
  color: #2c3e50;
  margin: 0 0 6px 0;
}

.widget-body p {
  font-size: 14px;
  color: #7f8c8d;
  margin: 0;
}

/* ========== 导航菜单 ========== */
.nav-widget {
  padding: 8px;
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 16px 18px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  border-radius: 12px;
  margin-bottom: 6px;
  font-weight: 500;
  font-size: 15px;
  color: #5a5e66;
}

.menu-item:last-child {
  margin-bottom: 0;
}

.menu-item:hover {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08), rgba(118, 75, 162, 0.08));
  transform: translateX(5px);
  color: #667eea;
}

.icon {
  margin-right: 14px;
  padding: 10px;
  border-radius: 12px;
  font-size: 18px;
  transition: all 0.3s ease;
}

.menu-item:hover .icon {
  transform: scale(1.1) rotate(5deg);
}

.blue {
  background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
  color: #667eea;
}

.purple {
  background: linear-gradient(135deg, #f3e8ff, #e9d5ff);
  color: #9333ea;
}

.yellow {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #f59e0b;
}

/* ========== 响应式优化 ========== */
@media (max-width: 1200px) {
  .navbar-content,
  .main-wrapper {
    padding-left: 24px;
    padding-right: 24px;
  }

  .hero-banner {
    padding: 0 40px;
    height: 280px;
  }

  .hero-content h1 {
    font-size: 36px;
  }
}

@media (max-width: 768px) {
  .nav-links {
    display: none;
  }

  .left-section {
    gap: 30px;
  }

  .content-grid {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
  }

  .hero-banner {
    height: 240px;
    padding: 0 24px;
  }

  .hero-content h1 {
    font-size: 28px;
  }

  .article-list {
    grid-template-columns: 1fr;
  }
}
</style>