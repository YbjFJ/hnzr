<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import { useArticleStore } from '../stores/article';
import { ElMessage } from 'element-plus';

// Props
const props = defineProps<{
  articleId: number;
  visible: boolean;
}>();

// Emits
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'save'): void;
}>();

const articleStore = useArticleStore();
const loading = ref(false);
const form = ref({
  title: '',
  summary: '',
  content: '',
  cover_image: '',
  source_name: '',
  origin_url: ''
});

// 监听visible变化，当显示时加载文章数据
watch(() => props.visible, (newVal) => {
  if (newVal) {
    loadArticleData();
  }
});

// 加载文章数据
const loadArticleData = async () => {
  loading.value = true;
  try {
    await articleStore.fetchArticle(props.articleId);
    const article = articleStore.currentArticle;
    if (article) {
      form.value = {
        title: article.title,
        summary: article.summary || '',
        content: article.content,
        cover_image: article.cover_image || '',
        source_name: article.source_name || '',
        origin_url: article.origin_url || ''
      };
    }
  } catch (error) {
    console.error('加载文章数据失败:', error);
    ElMessage.error('加载文章数据失败，请重试');
  } finally {
    loading.value = false;
  }
};

// 保存文章
const saveArticle = async () => {
  loading.value = true;
  try {
    await articleStore.updateArticle(props.articleId, form.value);
    ElMessage.success('文章保存成功');
    emit('save');
    emit('close');
  } catch (error) {
    console.error('保存文章失败:', error);
    ElMessage.error('保存文章失败，请重试');
  } finally {
    loading.value = false;
  }
};

// 关闭编辑框
const closeEditor = () => {
  emit('close');
};
</script>

<template>
  <el-dialog
    v-model="props.visible"
    title="编辑文章"
    width="80%"
    max-width="700px"
    @close="closeEditor"
    top="20px"
    :destroy-on-close="true"
  >
    <el-form
      :model="form"
      label-position="top"
      size="medium"
      v-loading="loading"
      :element-loading-text="'加载中...'"
    >
      <el-form-item
        label="标题"
        prop="title"
        :rules="[{ required: true, message: '请输入文章标题', trigger: 'blur' }]"
      >
        <el-input
          v-model="form.title"
          placeholder="请输入文章标题"
          size="medium"
        />
      </el-form-item>
      
      <el-form-item label="摘要">
        <el-input
          v-model="form.summary"
          type="textarea"
          placeholder="请输入文章摘要(列表页展示)"
          :rows="2"
          size="medium"
        />
      </el-form-item>
      
      <el-form-item
        label="正文"
        prop="content"
        :rules="[{ required: true, message: '请输入文章正文', trigger: 'blur' }]"
      >
        <el-input
          v-model="form.content"
          type="textarea"
          placeholder="请输入文章正文(HTML或Markdown)"
          :rows="10"
          size="medium"
        />
      </el-form-item>
      
      <el-form-item label="封面图URL">
        <el-input
          v-model="form.cover_image"
          placeholder="请输入封面图URL"
          size="medium"
        />
      </el-form-item>
      
      <el-form-item label="来源">
        <el-input
          v-model="form.source_name"
          placeholder="请输入文章来源"
          size="medium"
        />
      </el-form-item>
      
      <el-form-item label="原始链接">
        <el-input
          v-model="form.origin_url"
          type="textarea"
          placeholder="请输入原始链接(方便回溯)"
          :rows="3"
          size="medium"
        />
      </el-form-item>
    </el-form>
    
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="closeEditor" size="medium">取消</el-button>
        <el-button type="primary" @click="saveArticle" :loading="loading" size="medium">保存</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<style scoped>
/* ========== 对话框样式优化 ========== */
:deep(.el-dialog) {
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

:deep(.el-dialog__header) {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
  padding: 24px 28px;
  border-bottom: 2px solid rgba(102, 126, 234, 0.1);
  margin: 0;
}

:deep(.el-dialog__title) {
  font-size: 20px;
  font-weight: 700;
  color: #2c3e50;
  letter-spacing: -0.5px;
}

:deep(.el-dialog__headerbtn .el-dialog__close) {
  color: #6b7280;
  font-size: 20px;
  transition: all 0.3s ease;
}

:deep(.el-dialog__headerbtn:hover .el-dialog__close) {
  color: #667eea;
  transform: rotate(90deg);
}

:deep(.el-dialog__body) {
  padding: 28px;
}

:deep(.el-dialog__footer) {
  padding: 20px 28px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.02), rgba(118, 75, 162, 0.02));
  border-top: 2px solid rgba(102, 126, 234, 0.1);
}

/* ========== 表单样式优化 ========== */
:deep(.el-form-item__label) {
  font-weight: 600;
  color: #2c3e50;
  font-size: 14px;
}

:deep(.el-input__wrapper) {
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  border: 2px solid #e5e7eb;
  transition: all 0.3s ease;
  background: #f9fafb;
}

:deep(.el-input__wrapper:hover) {
  border-color: #667eea;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.1);
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #667eea;
  background: white;
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
}

:deep(.el-textarea__inner) {
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  border: 2px solid #e5e7eb;
  transition: all 0.3s ease;
  background: #f9fafb;
  font-family: inherit;
  line-height: 1.6;
}

:deep(.el-textarea__inner:hover) {
  border-color: #667eea;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.1);
}

:deep(.el-textarea__inner:focus) {
  border-color: #667eea;
  background: white;
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
}

/* ========== 按钮样式优化 ========== */
:deep(.el-button--default) {
  border: 2px solid #e5e7eb;
  border-radius: 20px;
  font-weight: 600;
  transition: all 0.3s ease;
}

:deep(.el-button--default:hover) {
  border-color: #667eea;
  color: #667eea;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  border-radius: 20px;
  font-weight: 600;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
  transition: all 0.3s ease;
}

:deep(.el-button--primary:hover) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

/* ========== 对话框动画 ========== */
:deep(.el-dialog) {
  animation: dialogFadeIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes dialogFadeIn {
  from {
    opacity: 0;
    transform: translateY(-30px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* ========== 响应式设计 ========== */
@media (max-width: 768px) {
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 20px auto;
  }

  :deep(.el-dialog__body) {
    padding: 20px;
  }

  :deep(.el-dialog__footer) {
    padding: 16px 20px;
  }
}
</style>
