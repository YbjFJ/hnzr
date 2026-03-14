<script setup lang="ts">
import { ref, reactive, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '../stores/user';
import { userApi } from '../services/api';
import { ElMessage } from 'element-plus';
import { User, Lock, Monitor, ArrowRight, CircleCheck } from '@element-plus/icons-vue';

const router = useRouter();
const userStore = useUserStore();
const formRef = ref();
const loading = ref(false);

// 切换登录/注册模式
const isLoginMode = ref(true);

// 登录表单
const loginForm = reactive({ email: '', password: '' });

// 注册表单
const registerForm = reactive({
  email: '',
  password: '',
  confirmPassword: '',
  nickname: ''
});

// 登录表单规则
const loginRules = {
  email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
};

// 注册表单规则
const registerRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule: Record<string, any>, value: string, callback: (error?: Error | undefined) => void) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入的密码不一致'));
        } else {
          callback();
        }
      },
      trigger: 'blur'
    }
  ],
  nickname: [
    { max: 20, message: '昵称长度不能超过20位', trigger: 'blur' }
  ]
};

// 登录处理
const handleLogin = async () => {
  if (!formRef.value) return;
  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      loading.value = true;
      try {
        await userStore.login(loginForm.email, loginForm.password);
        ElMessage.success('登录成功');
        router.replace('/');
      } catch {
        ElMessage.error('登录失败');
      } finally {
        loading.value = false;
      }
    }
  });
};

// 注册处理
const handleRegister = async () => {
  if (!formRef.value) return;
  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      loading.value = true;
      try {
        await userStore.register(registerForm.email, registerForm.password, registerForm.nickname);
        ElMessage.success('注册成功');
        // 注册成功后切换到登录模式
        isLoginMode.value = true;
      } catch (err) {
        ElMessage.error(err instanceof Error ? err.message : '注册失败，请稍后重试');
      } finally {
        loading.value = false;
      }
    }
  });
};

// 切换模式
const toggleMode = () => {
  isLoginMode.value = !isLoginMode.value;
};

// 忘记密码弹窗：步骤 1=输入邮箱发验证码，2=输入验证码+新密码，3=成功
const showForgotDialog = ref(false);
const forgotStep = ref(1);
const forgotForm = reactive({
  email: '',
  code: '',
  newPassword: '',
  confirmPassword: ''
});
const forgotLoading = ref(false);
const forgotFormRef = ref();
const forgotCodeCountdown = ref(0);
let forgotCodeTimer: ReturnType<typeof setInterval> | null = null;

const forgotRules = {
  email: [
    { required: true, message: '请输入注册时使用的邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { min: 6, max: 6, message: '验证码为 6 位数字', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_: unknown, value: string, cb: (e?: Error) => void) => {
        if (value !== forgotForm.newPassword) cb(new Error('两次输入的密码不一致'));
        else cb();
      },
      trigger: 'blur'
    }
  ]
};

const openForgotDialog = () => {
  showForgotDialog.value = true;
  forgotStep.value = 1;
  forgotForm.email = '';
  forgotForm.code = '';
  forgotForm.newPassword = '';
  forgotForm.confirmPassword = '';
  forgotCodeCountdown.value = 0;
  if (forgotCodeTimer) {
    clearInterval(forgotCodeTimer);
    forgotCodeTimer = null;
  }
};

const closeForgotDialog = () => {
  showForgotDialog.value = false;
  if (forgotCodeTimer) {
    clearInterval(forgotCodeTimer);
    forgotCodeTimer = null;
  }
};

const startCodeCountdown = () => {
  forgotCodeCountdown.value = 60;
  forgotCodeTimer = setInterval(() => {
    forgotCodeCountdown.value--;
    if (forgotCodeCountdown.value <= 0 && forgotCodeTimer) {
      clearInterval(forgotCodeTimer);
      forgotCodeTimer = null;
    }
  }, 1000);
};

onUnmounted(() => {
  if (forgotCodeTimer) clearInterval(forgotCodeTimer);
});

// 发送验证码
const handleSendCode = async () => {
  if (!forgotFormRef.value) return;
  const valid = await forgotFormRef.value.validateField('email').catch(() => false);
  if (!valid) return;
  forgotLoading.value = true;
  try {
    const res = await userApi.sendForgotCode(forgotForm.email);
    ElMessage.success(res.message || '验证码已发送');
    forgotStep.value = 2;
    startCodeCountdown();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '发送失败，请稍后重试');
  } finally {
    forgotLoading.value = false;
  }
};

// 提交重置密码
const handleForgotResetSubmit = async () => {
  if (!forgotFormRef.value) return;
  await forgotFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return;
    forgotLoading.value = true;
    try {
      const res = await userApi.resetPasswordWithCode({
        email: forgotForm.email,
        code: forgotForm.code,
        new_password: forgotForm.newPassword
      });
      ElMessage.success(res.message || '密码已重置');
      forgotStep.value = 3;
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '重置失败，请稍后重试');
    } finally {
      forgotLoading.value = false;
    }
  });
};
</script>

<template>
  <div class="login-container">
    <!-- 左侧全屏背景图区域 -->
    <div class="left-banner">
      <div class="glass-layer">
        <div class="brand-box">
          <el-icon :size="60" class="logo-icon"><Monitor /></el-icon>
          <h1 class="brand-title">农业融资政策解读平台</h1>
          <p class="brand-slogan">构建您的专属 AI 政策咨询平台</p>
        </div>
        <div class="brand-footer">
          <p>© 2026 HuiNongRongZhou Inc.</p>
        </div>
      </div>
    </div>

    <!-- 右侧全屏表单区域 -->
    <div class="right-form">
      <div class="form-wrapper">
        <div class="welcome-text">
          <h2>{{ isLoginMode ? '欢迎回来' : '创建账号' }}</h2>
          <p>{{ isLoginMode ? '请登录您的账号以继续' : '注册新账号，开启智能之旅' }}</p>
        </div>

        <!-- 登录/注册表单切换 -->
        <div class="mode-switch">
          <span 
            :class="['switch-btn', { active: isLoginMode }]" 
            @click="toggleMode"
          >
            登录
          </span>
          <span 
            :class="['switch-btn', { active: !isLoginMode }]" 
            @click="toggleMode"
          >
            注册
          </span>
        </div>

        <!-- 登录表单 -->
        <el-form 
          v-if="isLoginMode"
          ref="formRef" 
          :model="loginForm" 
          :rules="loginRules" 
          size="large" 
          class="custom-form"
          @keyup.enter="handleLogin"
        >
          <el-form-item prop="email">
            <el-input 
              v-model="loginForm.email" 
              placeholder="请输入邮箱" 
              :prefix-icon="User"
              class="huge-input"
              :disabled="loading"
            />
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input 
              v-model="loginForm.password" 
              placeholder="请输入密码" 
              type="password" 
              show-password 
              :prefix-icon="Lock"
              class="huge-input"
              :disabled="loading"
            />
          </el-form-item>

          <div class="form-options">
            <el-checkbox>自动登录</el-checkbox>
            <el-link type="primary" :underline="false" @click="openForgotDialog">忘记密码？</el-link>
          </div>

          <el-button 
            type="primary" 
            class="submit-btn" 
            :loading="loading"
            @click="handleLogin"
          >
            立即登录 <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </el-form>

        <!-- 注册表单 -->
        <el-form 
          v-else
          ref="formRef" 
          :model="registerForm" 
          :rules="registerRules" 
          size="large" 
          class="custom-form"
          @keyup.enter="handleRegister"
        >
          <el-form-item prop="email">
            <el-input 
              v-model="registerForm.email" 
              placeholder="请输入邮箱" 
              :prefix-icon="User"
              class="huge-input"
              :disabled="loading"
              clearable
            />
          </el-form-item>
          
          <el-form-item prop="nickname">
            <el-input 
              v-model="registerForm.nickname" 
              placeholder="请输入昵称" 
              :prefix-icon="User"
              class="huge-input"
              :disabled="loading"
              clearable
            />
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input 
              v-model="registerForm.password" 
              placeholder="请输入密码" 
              type="password" 
              show-password 
              :prefix-icon="Lock"
              class="huge-input"
              :disabled="loading"
              clearable
            />
          </el-form-item>
          
          <el-form-item prop="confirmPassword">
            <el-input 
              v-model="registerForm.confirmPassword" 
              placeholder="请再次输入密码" 
              type="password" 
              show-password 
              :prefix-icon="Lock"
              class="huge-input"
              :disabled="loading"
              clearable
            />
          </el-form-item>

          <el-button 
            type="primary" 
            class="submit-btn" 
            :loading="loading"
            @click="handleRegister"
          >
            立即注册 <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </el-form>
      </div>
    </div>

    <!-- 忘记密码弹窗：验证码流程 -->
    <el-dialog
      v-model="showForgotDialog"
      title="找回密码"
      width="420px"
      align-center
      :close-on-click-modal="!forgotLoading"
      destroy-on-close
      class="forgot-dialog"
      @close="closeForgotDialog"
    >
      <!-- 步骤 1：输入邮箱，发送验证码 -->
      <div v-if="forgotStep === 1" class="forgot-form">
        <p class="forgot-tip">请输入注册时使用的邮箱，我们将发送 6 位验证码，15 分钟内有效。</p>
        <el-form ref="forgotFormRef" :model="forgotForm" :rules="forgotRules" label-position="top">
          <el-form-item label="邮箱" prop="email">
            <el-input
              v-model="forgotForm.email"
              placeholder="请输入邮箱"
              :prefix-icon="User"
              size="large"
              :disabled="forgotLoading"
              clearable
              @keyup.enter="handleSendCode"
            />
          </el-form-item>
          <el-button
            type="primary"
            class="forgot-submit"
            :loading="forgotLoading"
            :disabled="forgotCodeCountdown > 0"
            @click="handleSendCode"
          >
            {{ forgotCodeCountdown > 0 ? `${forgotCodeCountdown}s 后重新发送` : '发送验证码' }}
          </el-button>
        </el-form>
      </div>

      <!-- 步骤 2：输入验证码与新密码 -->
      <div v-else-if="forgotStep === 2" class="forgot-form">
        <p class="forgot-tip">验证码已发送至 <strong>{{ forgotForm.email }}</strong>，请查收后填写验证码并设置新密码。</p>
        <el-form
          ref="forgotFormRef"
          :model="forgotForm"
          :rules="forgotRules"
          label-position="top"
          @keyup.enter="handleForgotResetSubmit"
        >
          <el-form-item label="验证码" prop="code">
            <el-input
              v-model="forgotForm.code"
              placeholder="请输入 6 位验证码"
              size="large"
              maxlength="6"
              :disabled="forgotLoading"
              clearable
            />
          </el-form-item>
          <el-form-item label="新密码" prop="newPassword">
            <el-input
              v-model="forgotForm.newPassword"
              type="password"
              show-password
              placeholder="请输入新密码（至少 6 位）"
              :prefix-icon="Lock"
              size="large"
              :disabled="forgotLoading"
              clearable
            />
          </el-form-item>
          <el-form-item label="确认新密码" prop="confirmPassword">
            <el-input
              v-model="forgotForm.confirmPassword"
              type="password"
              show-password
              placeholder="请再次输入新密码"
              :prefix-icon="Lock"
              size="large"
              :disabled="forgotLoading"
              clearable
            />
          </el-form-item>
          <div class="forgot-actions">
            <el-button @click="forgotStep = 1">更换邮箱</el-button>
            <el-button
              type="primary"
              class="forgot-submit"
              :loading="forgotLoading"
              @click="handleForgotResetSubmit"
            >
              确认重置密码
            </el-button>
          </div>
        </el-form>
      </div>

      <!-- 步骤 3：成功 -->
      <div v-else class="forgot-success">
        <el-icon :size="48" color="#67c23a"><CircleCheck /></el-icon>
        <p class="success-title">密码已重置</p>
        <p class="success-desc">请使用新密码登录。</p>
        <el-button type="primary" @click="closeForgotDialog">关闭</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: white;
}

/* 左侧样式 */
.left-banner {
  flex: 1.5; /* 占据 60% 宽度 */
  background-image: url('https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop');
  background-size: cover;
  background-position: center;
  position: relative;
}

.glass-layer {
  width: 100%;
  height: 100%;
  background: rgba(18, 28, 56, 0.75); /* 深蓝色遮罩 */
  backdrop-filter: blur(4px);
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 100px;
  color: white;
}

.brand-box {
  animation: slideUp 0.8s ease-out;
}

.logo-icon {
  margin-bottom: 20px;
  color: #409eff;
}

.brand-title {
  font-size: 48px;
  font-weight: 800;
  margin: 0 0 16px 0;
  letter-spacing: 2px;
}

.brand-slogan {
  font-size: 20px;
  opacity: 0.8;
  font-weight: 300;
}

.brand-footer {
  position: absolute;
  bottom: 40px;
  opacity: 0.5;
  font-size: 14px;
}

/* 右侧样式 */
.right-form {
  flex: 1; /* 占据 40% 宽度 */
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  padding: 40px;
}

.form-wrapper {
  width: 100%;
  max-width: 420px; /* 限制表单最大宽度，防止太宽难看 */
  animation: fadeIn 1s ease-out;
}

.welcome-text {
  margin-bottom: 40px;
}
.welcome-text h2 { font-size: 32px; color: #333; margin: 0 0 10px 0; }
.welcome-text p { color: #999; font-size: 16px; margin: 0; }

/* 输入框加大 */
.huge-input :deep(.el-input__wrapper) {
  padding: 12px 15px;
  height: 50px; /* 更高 */
  background-color: #f5f7fa;
  box-shadow: none !important; /* 去掉默认边框 */
  border-radius: 8px;
}
.huge-input :deep(.el-input__wrapper.is-focus) {
  background-color: white;
  box-shadow: 0 0 0 1px #409eff !important;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 20px 0 30px;
}

.submit-btn {
  width: 100%;
  height: 50px;
  font-size: 18px;
  border-radius: 8px;
  font-weight: 600;
  background: linear-gradient(90deg, #409eff 0%, #3a8ee6 100%);
  border: none;
}
.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(64, 158, 255, 0.3);
}

.mode-switch {
  display: flex;
  margin-bottom: 30px;
  border-radius: 8px;
  background-color: #f5f7fa;
  overflow: hidden;
}

.switch-btn {
  flex: 1;
  text-align: center;
  padding: 12px 0;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #666;
}

.switch-btn.active {
  background-color: #409eff;
  color: white;
  font-weight: 600;
}

.switch-btn:hover {
  background-color: #eef4ff;
  color: #409eff;
}

.switch-btn.active:hover {
  background-color: #368ce7;
  color: white;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* 忘记密码弹窗 */
.forgot-dialog :deep(.el-dialog__header) {
  margin-right: 0;
  padding-bottom: 16px;
}
.forgot-dialog :deep(.el-dialog__body) {
  padding-top: 0;
}
.forgot-tip {
  color: #666;
  font-size: 14px;
  margin: 0 0 20px 0;
  line-height: 1.6;
}
.forgot-form .el-form-item {
  margin-bottom: 20px;
}
.forgot-submit {
  width: 100%;
  height: 44px;
  font-size: 16px;
  border-radius: 8px;
}
.forgot-success {
  text-align: center;
  padding: 10px 0;
}
.forgot-success .success-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 16px 0 8px 0;
}
.forgot-success .success-desc {
  color: #666;
  font-size: 14px;
  line-height: 1.6;
  margin: 0 0 24px 0;
}
.forgot-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.forgot-actions .forgot-submit {
  flex: 1;
  margin-left: 12px;
}

/* 响应式调整：屏幕太窄变成单列 */
@media (max-width: 1024px) {
  .left-banner { display: none; }
  .right-form { flex: 1; }
}
</style>