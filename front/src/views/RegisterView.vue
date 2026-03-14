<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '../stores/user';
import { ElMessage } from 'element-plus';

const router = useRouter();
const userStore = useUserStore();

const form = reactive({
  email: '',
  password: '',
  confirmPassword: '',
  nickname: ''
});

const rules = {
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
      validator: (rule: any, value: string, callback: any) => {
        if (value !== form.password) {
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

const loading = ref(false);
const formRef = ref();

const handleRegister = async () => {
  if (!formRef.value) return;
  
  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      loading.value = true;
      
      try {
        await userStore.register(form.email, form.password, form.nickname);
        // 注册成功后跳转到首页
        router.push('/');
        ElMessage.success('注册成功');
      } catch (err) {
        ElMessage.error(err instanceof Error ? err.message : '注册失败，请稍后重试');
      } finally {
        loading.value = false;
      }
    }
  });
};

// 跳转到登录页面
const goToLogin = () => {
  router.push('/login');
};
</script>

<template>
  <div class="register-container">
    <div class="register-form">
      <h2>注册</h2>
      
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="邮箱" prop="email">
          <el-input 
            v-model="form.email"
            placeholder="请输入邮箱"
            type="email"
            :disabled="loading"
            clearable
          />
        </el-form-item>
        
        <el-form-item label="昵称" prop="nickname">
          <el-input 
            v-model="form.nickname"
            placeholder="请输入昵称"
            :disabled="loading"
            clearable
          />
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input 
            v-model="form.password"
            placeholder="请输入密码"
            type="password"
            :disabled="loading"
            show-password
            clearable
          />
        </el-form-item>
        
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input 
            v-model="form.confirmPassword"
            placeholder="请再次输入密码"
            type="password"
            :disabled="loading"
            show-password
            clearable
          />
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            @click="handleRegister"
            :loading="loading"
            style="width: 100%"
          >
            注册
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-link">
        <span>已有账号？</span>
        <el-button type="text" @click="goToLogin">登录</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f5f7fa;
}

.register-form {
  background-color: white;
  padding: 40px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 400px;
}

.register-form h2 {
  margin: 0 0 30px 0;
  font-size: 24px;
  font-weight: 600;
  color: #333;
  text-align: center;
}

.login-link {
  text-align: center;
  font-size: 14px;
  color: #666;
  margin-top: 20px;
}
</style>