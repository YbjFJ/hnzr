<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '../stores/user';
import { userApi } from '../services/api';
import type { User } from '../types/user';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Search, Plus, Edit, Delete, RefreshRight, UserFilled, ArrowLeft } from '@element-plus/icons-vue';

const router = useRouter();
const userStore = useUserStore();

const loading = ref(false);
const list = ref<User[]>([]);
const keyword = ref('');
const skip = ref(0);
const limit = ref(20);

const isAdmin = computed(() => userStore.isAdmin);

// 新增/编辑弹窗
const dialogVisible = ref(false);
const dialogTitle = ref('新增用户');
const dialogLoading = ref(false);
const formRef = ref();
const form = ref<{
  id?: number;
  email: string;
  password: string;
  nickname: string;
  role: string;
  is_active: boolean;
  new_password?: string;
}>({
  email: '',
  password: '',
  nickname: '',
  role: 'user',
  is_active: true
});

const formRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码不少于6位', trigger: 'blur' }
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }]
};

function isCreate() {
  return !form.value.id;
}

async function loadList() {
  if (!userStore.isAdmin) return;
  loading.value = true;
  try {
    list.value = await userApi.getUsers({
      skip: skip.value,
      limit: limit.value,
      keyword: keyword.value || undefined
    });
  } catch (e) {
    ElMessage.error((e as Error).message || '加载用户列表失败');
  } finally {
    loading.value = false;
  }
}

function onSearch() {
  skip.value = 0;
  loadList();
}

watch(keyword, () => {
  if (!keyword.value) {
    skip.value = 0;
    loadList();
  }
});

function openCreate() {
  dialogTitle.value = '新增用户';
  form.value = {
    email: '',
    password: '',
    nickname: '',
    role: 'user',
    is_active: true
  };
  dialogVisible.value = true;
}

function openEdit(row: User) {
  dialogTitle.value = '编辑用户';
  form.value = {
    id: row.id,
    email: row.email,
    password: '',
    nickname: row.nickname || '',
    role: (row.role as string) || 'user',
    is_active: row.is_active ?? true,
    new_password: ''
  };
  dialogVisible.value = true;
}

async function submitDialog() {
  if (!formRef.value) return;
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return;
    if (isCreate() && !form.value.password) {
      ElMessage.warning('请输入密码');
      return;
    }
    dialogLoading.value = true;
    try {
      if (isCreate()) {
        await userApi.createUser({
          email: form.value.email,
          password: form.value.password,
          nickname: form.value.nickname || undefined,
          role: form.value.role
        });
        ElMessage.success('创建成功');
      } else {
        const payload: Parameters<typeof userApi.adminUpdateUser>[1] = {
          nickname: form.value.nickname || undefined,
          role: form.value.role,
          is_active: form.value.is_active
        };
        if (form.value.new_password && form.value.new_password.length >= 6) {
          payload.new_password = form.value.new_password;
        }
        await userApi.adminUpdateUser(form.value.id!, payload);
        ElMessage.success('更新成功');
      }
      dialogVisible.value = false;
      loadList();
    } catch (e) {
      ElMessage.error((e as Error).message || '操作失败');
    } finally {
      dialogLoading.value = false;
    }
  });
}

function handleDelete(row: User) {
  ElMessageBox.confirm(`确定删除用户「${row.email}」？此操作不可恢复。`, '删除确认', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await userApi.deleteUser(row.id);
      ElMessage.success('已删除');
      loadList();
    } catch (e) {
      ElMessage.error((e as Error).message || '删除失败');
    }
  }).catch(() => {});
}

onMounted(() => {
  if (!userStore.isLoggedIn) {
    router.replace('/login');
    return;
  }
  if (!userStore.isAdmin) {
    ElMessage.warning('仅管理员可访问用户管理');
    router.replace('/');
    return;
  }
  loadList();
});
</script>

<template>
  <div class="user-manage">
    <!-- 顶部导航条 -->
    <header class="top-bar">
      <a class="back-link" @click="router.push('/')">
        <el-icon><ArrowLeft /></el-icon>
        <span>返回首页</span>
      </a>
    </header>

    <div class="content-wrap">
      <!-- 页面标题区 -->
      <div class="page-header">
        <div class="header-icon">
          <el-icon><UserFilled /></el-icon>
        </div>
        <div class="header-text">
          <h1>用户管理</h1>
          <p class="desc">仅管理员可进行用户的增删改查</p>
        </div>
      </div>

      <!-- 工具栏卡片 -->
      <div class="toolbar-card">
        <el-input
          v-model="keyword"
          placeholder="搜索邮箱或昵称"
          clearable
          class="search-input"
          @keyup.enter="onSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" class="btn-primary" :icon="Search" @click="onSearch">
          搜索
        </el-button>
        <el-button class="btn-default" :icon="Plus" @click="openCreate">新增用户</el-button>
        <el-button class="btn-default" :icon="RefreshRight" @click="loadList">刷新</el-button>
      </div>

      <!-- 表格卡片 -->
      <div class="table-card">
        <el-table
          v-loading="loading"
          :data="list"
          class="table"
          :header-cell-style="{ background: 'var(--el-fill-color-light)', fontWeight: 600 }"
        >
          <el-table-column prop="id" label="ID" width="72" align="center" />
          <el-table-column prop="email" label="邮箱" min-width="200" show-overflow-tooltip />
          <el-table-column prop="nickname" label="昵称" min-width="120">
            <template #default="{ row }">
              <span class="cell-nickname">{{ row.nickname || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="role" label="角色" width="100" align="center">
            <template #default="{ row }">
              <span :class="['role-tag', (row.role as string) === 'admin' ? 'role-admin' : 'role-user']">
                {{ (row.role as string) === 'admin' ? '管理员' : '用户' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="is_active" label="状态" width="90" align="center">
            <template #default="{ row }">
              <span :class="['status-dot', row.is_active ? 'active' : 'inactive']" />
              {{ row.is_active ? '激活' : '禁用' }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="176">
            <template #default="{ row }">
              {{ row.created_at ? new Date(row.created_at).toLocaleString() : '—' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right" align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" class="action-btn" :icon="Edit" @click="openEdit(row)">
                编辑
              </el-button>
              <el-button link type="danger" size="small" class="action-btn" :icon="Delete" @click="handleDelete(row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="!loading && list.length === 0" class="empty-state">
          <el-icon class="empty-icon"><UserFilled /></el-icon>
          <p>暂无用户数据</p>
          <el-button type="primary" class="btn-primary" :icon="Plus" @click="openCreate">新增用户</el-button>
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="480px"
      destroy-on-close
      class="form-dialog"
      @close="formRef?.resetFields?.()"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="isCreate() ? formRules : { ...formRules, password: [] }"
        label-width="90px"
        class="dialog-form"
      >
        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model="form.email"
            placeholder="登录邮箱"
            :disabled="!isCreate()"
            size="large"
          />
        </el-form-item>
        <el-form-item v-if="isCreate()" label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="不少于6位" show-password size="large" />
        </el-form-item>
        <el-form-item v-else label="新密码">
          <el-input
            v-model="form.new_password"
            type="password"
            placeholder="不填则不修改"
            show-password
            size="large"
          />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" placeholder="选填" size="large" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" placeholder="选择角色" style="width: 100%" size="large">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!isCreate()" label="状态">
          <el-switch v-model="form.is_active" active-text="激活" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button size="large" @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" size="large" class="btn-primary" :loading="dialogLoading" @click="submitDialog">
            确定
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-manage {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  padding: 0;
  box-sizing: border-box;
}

/* 顶部栏 */
.top-bar {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(12px);
  padding: 12px 32px;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.06);
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #5a5e66;
  cursor: pointer;
  transition: color 0.2s, transform 0.2s;
}

.back-link:hover {
  color: #667eea;
  transform: translateX(-2px);
}

.content-wrap {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
}

/* 页面标题 */
.page-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 28px;
  animation: fadeInUp 0.5s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.header-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.35);
}

.header-text h1 {
  font-size: 26px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0 0 6px 0;
  letter-spacing: -0.5px;
}

.header-text .desc {
  font-size: 14px;
  color: #7f8c8d;
  margin: 0;
}

/* 工具栏 */
.toolbar-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 24px;
  background: #fff;
  border-radius: 16px;
  margin-bottom: 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(0, 0, 0, 0.04);
  animation: fadeInUp 0.5s ease-out 0.1s backwards;
}

.search-input {
  width: 280px;
}

.search-input :deep(.el-input__wrapper) {
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 10px;
  font-weight: 500;
}

.btn-primary:hover {
  opacity: 0.92;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.btn-default {
  border-radius: 10px;
  font-weight: 500;
}

/* 表格卡片 */
.table-card {
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(0, 0, 0, 0.04);
  position: relative;
  animation: fadeInUp 0.5s ease-out 0.15s backwards;
}

.table :deep(.el-table__header th) {
  font-size: 13px;
  color: #5a5e66;
}

.table :deep(.el-table__body td) {
  font-size: 14px;
}

.table :deep(.el-table__row:hover) {
  background: rgba(102, 126, 234, 0.04) !important;
}

.table :deep(.el-table__inner-wrapper::after) {
  display: none;
}

.cell-nickname {
  color: #2c3e50;
}

.role-tag {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.role-admin {
  background: linear-gradient(135deg, rgba(245, 108, 108, 0.2) 0%, rgba(238, 82, 83, 0.25) 100%);
  color: #c0392b;
}

.role-user {
  background: rgba(102, 126, 234, 0.12);
  color: #667eea;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

.status-dot.active {
  background: #67c23a;
  box-shadow: 0 0 0 2px rgba(103, 194, 58, 0.3);
}

.status-dot.inactive {
  background: #c0c4cc;
}

.action-btn {
  font-weight: 500;
}

/* 空状态 */
.empty-state {
  padding: 60px 24px;
  text-align: center;
}

.empty-icon {
  font-size: 64px;
  color: #dcdfe6;
  margin-bottom: 16px;
}

.empty-state p {
  font-size: 15px;
  color: #909399;
  margin: 0 0 20px 0;
}

/* 弹窗 */
.form-dialog :deep(.el-dialog__header) {
  padding: 20px 24px 16px;
  border-bottom: 1px solid #f0f2f5;
}

.form-dialog :deep(.el-dialog__title) {
  font-size: 18px;
  font-weight: 600;
  color: #2c3e50;
}

.form-dialog :deep(.el-dialog__body) {
  padding: 24px 24px 20px;
}

.dialog-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.dialog-footer .btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.dialog-footer .btn-primary:hover {
  opacity: 0.92;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
</style>
