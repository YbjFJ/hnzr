<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '../stores/user';
import { ElMessage } from 'element-plus';

const router = useRouter();
const userStore = useUserStore();

// 用户信息
const user = computed(() => userStore.user);

// 激活的标签页
const activeTab = ref('profile');

// 个人资料表单
const profileForm = ref({
  nickname: user.value?.nickname || '',
  avatar: user.value?.avatar || ''
});

// 修改密码表单
const passwordForm = ref({
  old_password: '',
  new_password: ''
});

// 表单验证规则
const profileRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    { min: 2, max: 20, message: '昵称长度在 2 到 20 个字符', trigger: 'blur' }
  ]
};

const passwordRules = {
  old_password: [
    { required: true, message: '请输入旧密码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码长度不能少于 6 个字符', trigger: 'blur' }
  ]
};

// 表单引用
const profileFormRef = ref();
const passwordFormRef = ref();

// 页面加载时获取用户信息
onMounted(() => {
  if (userStore.isLoggedIn && userStore.user?.id) {
    userStore.fetchCurrentUser();
    // 初始化表单数据
    profileForm.value = {
      nickname: user.value?.nickname || '',
      avatar: user.value?.avatar || ''
    };
  } else {
    router.push('/login');
  }
});

// 更新个人资料
const updateProfile = async () => {
  if (!profileFormRef.value) return;
  
  await profileFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      try {
        await userStore.updateProfile(profileForm.value);
        ElMessage.success('个人资料更新成功');
      } catch (error) {
        ElMessage.error((error as Error).message || '更新失败');
      }
    }
  });
};

// 修改密码
const updatePassword = async () => {
  if (!passwordFormRef.value) return;
  
  await passwordFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      try {
        await userStore.updatePassword(passwordForm.value);
        ElMessage.success('密码修改成功');
        // 清空表单
        passwordForm.value = {
          old_password: '',
          new_password: ''
        };
      } catch (error) {
        ElMessage.error((error as Error).message || '修改失败');
      }
    }
  });
};
</script>

<template>
  <div class="profile-layout">
    <!-- 顶部导航 -->
    <header class="navbar">
      <div class="navbar-content">
        <div class="left-section">
          <div class="logo-area" @click="router.push('/')">
            <div class="logo-box">G</div>
            <span class="logo-text">AI 智能资讯与咨询平台</span>
          </div>
        </div>
        <div class="right-area">
          <el-button type="primary" round @click="router.push('/')">返回首页</el-button>
        </div>
      </div>
    </header>

    <!-- 主内容 -->
    <main class="profile-content">
      <div class="profile-container">
        <h1>个人中心</h1>
        
        <!-- 标签页 -->
        <el-tabs v-model="activeTab" class="profile-tabs">
          <!-- 个人资料 -->
          <el-tab-pane label="个人资料" name="profile">
            <el-form
              ref="profileFormRef"
              :model="profileForm"
              :rules="profileRules"
              label-width="100px"
              class="profile-form"
            >
              <el-form-item label="邮箱">
                <el-input :model-value="user?.email" disabled placeholder="用户邮箱" />
              </el-form-item>
              
              <el-form-item label="昵称" prop="nickname">
                <el-input v-model="profileForm.nickname" placeholder="请输入昵称" />
              </el-form-item>
              
              <el-form-item label="头像">
                <el-input v-model="profileForm.avatar" placeholder="请输入头像URL" />
                <div class="avatar-preview">
                  <img v-if="profileForm.avatar" :src="profileForm.avatar" alt="头像预览" />
                  <div v-else class="avatar-placeholder">暂无头像</div>
                </div>
              </el-form-item>
              
              <el-form-item>
                <el-button type="primary" @click="updateProfile" :loading="userStore.loading">保存修改</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
          
          <!-- 修改密码 -->
          <el-tab-pane label="修改密码" name="password">
            <el-form
              ref="passwordFormRef"
              :model="passwordForm"
              :rules="passwordRules"
              label-width="100px"
              class="profile-form"
            >
              <el-form-item label="旧密码" prop="old_password">
                <el-input v-model="passwordForm.old_password" type="password" placeholder="请输入旧密码" />
              </el-form-item>
              
              <el-form-item label="新密码" prop="new_password">
                <el-input v-model="passwordForm.new_password" type="password" placeholder="请输入新密码" />
              </el-form-item>
              
              <el-form-item>
                <el-button type="primary" @click="updatePassword" :loading="userStore.loading">修改密码</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
    </main>
  </div>
</template>

<style scoped>
.profile-layout {
  min-height: 100vh;
  background-color: #f4f6f9;
  display: flex;
  flex-direction: column;
}

/* 导航栏 */
.navbar {
  width: 100%;
  height: 64px;
  background: white;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  position: sticky;
  top: 0;
  z-index: 999;
}

.navbar-content {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 40px;
  box-sizing: border-box;
}

.left-section { display: flex; align-items: center; }
.logo-area { display: flex; align-items: center; gap: 10px; font-weight: bold; font-size: 20px; cursor: pointer; }
.logo-box { width: 32px; height: 32px; background: #409eff; color: white; border-radius: 6px; display: flex; align-items: center; justify-content: center; }

.right-area { display: flex; align-items: center; gap: 20px; }

/* 主内容 */
.profile-content {
  width: 100%;
  flex: 1;
  padding: 24px 40px;
  box-sizing: border-box;
}

.profile-container {
  max-width: 800px;
  margin: 0 auto;
  background: white;
  border-radius: 10px;
  padding: 30px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

.profile-container h1 {
  margin-bottom: 30px;
  font-size: 24px;
  color: #303133;
}

.profile-tabs {
  margin-bottom: 20px;
}

.profile-form {
  width: 100%;
}

.avatar-preview {
  margin-top: 10px;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  overflow: hidden;
  border: 2px solid #ebeef5;
}

.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  color: #909399;
  font-size: 12px;
}
</style>