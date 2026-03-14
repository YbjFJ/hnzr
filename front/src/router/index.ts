import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ArticlesView from '../views/ArticlesView.vue'
import ArticleDetailView from '../views/ArticleDetailView.vue'
import LoginView from '../views/LoginView.vue'
import ChatView from '../views/ChatView.vue'
import ReportsView from '../views/ReportsView.vue'
import FavoritesView from '../views/FavoritesView.vue'
import ProfileView from '../views/ProfileView.vue'
import UserManageView from '../views/UserManageView.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView
  },
  {
    path: '/articles',
    name: 'articles',
    component: ArticlesView
  },
  {
    path: '/articles/:id',
    name: 'article-detail',
    component: ArticleDetailView
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView
  },
  {
    path: '/chat',
    name: 'chat',
    component: ChatView
  },
  {
    path: '/reports',
    name: 'reports',
    component: ReportsView
  },
  {
    path: '/favorites',
    name: 'favorites',
    component: FavoritesView
  },
  {
    path: '/profile',
    name: 'profile',
    component: ProfileView
  },
  {
    path: '/admin/users',
    name: 'admin-users',
    component: UserManageView,
    meta: { requireAdmin: true }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: routes
})

// 管理员页面：未登录跳转登录，非管理员跳转首页
router.beforeEach(async (to, _from, next) => {
  if (to.meta.requireAdmin) {
    const token = localStorage.getItem('token');
    if (!token) {
      next({ path: '/login' });
      return;
    }
    // 依赖 pinia 的 userStore 在应用内已初始化，这里仅做路由放行，页面内再校验 isAdmin
    next();
    return;
  }
  next();
})

export default router
