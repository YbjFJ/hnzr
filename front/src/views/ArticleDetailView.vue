<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useArticleStore } from '../stores/article';
import { useUserStore } from '../stores/user';
import { favoriteApi, articleApi } from '../services/api';
import ArticleEditor from '../components/ArticleEditor.vue';
import type { Article } from '../types/article';
import { Star, StarFilled, EditPen, Back, VideoPlay, VideoPause, Document, Plus } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import MarkdownIt from 'markdown-it';

const route = useRoute();
const router = useRouter();
const articleStore = useArticleStore();
const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);

// 1. 初始化 Markdown 解析器
const md = new MarkdownIt({
  html: false,       // 为了安全性，默认不解析 HTML 标签
  breaks: true,      // 将换行符转换为 <br>
  linkify: true,     // 自动将 URL 转换为链接
  typographer: true  // 优化排版符号
});

const isFavorite = ref(false);
const loading = ref(false);
const showEditor = ref(false);

// 官方解读：仅当当前文章为新闻时展示
const isNews = computed(() => articleStore.currentArticle?.type === 'news');
const interpretations = ref<Article[]>([]);
const interpretationsLoading = ref(false);
const showAddInterpretationModal = ref(false);
const addInterpTitle = ref('');
const addInterpSummary = ref('');
const addInterpContent = ref('');
const addInterpCategoryId = ref<number | null>(null);
const addInterpSubmitting = ref(false);

// AI 流式生成解读正文
const showAiGenerateBox = ref(false);
const aiGenerateContent = ref('');
const aiGenerateLoading = ref(false);
const aiGenerateError = ref('');
const aiGenerateContentRef = ref<HTMLElement | null>(null);

// --- 语音播报相关状态 ---
const isSpeaking = ref(false); // 是否正在朗读（包含暂停状态的逻辑标记）
const isPaused = ref(false);   // 是否处于暂停状态
const synth = window.speechSynthesis; // 浏览器原生语音合成实例
let utterance: SpeechSynthesisUtterance | null = null; // 当前的语音片段对象

const articleId = computed(() => parseInt(route.params.id as string) || 0);

// 2. 计算属性：渲染正文 Markdown
const renderedContent = computed(() => {
  if (!articleStore.currentArticle?.content) return '';
  return md.render(articleStore.currentArticle.content);
});

// 3. 计算属性：渲染摘要 Markdown
const renderedSummary = computed(() => {
  if (!articleStore.currentArticle?.summary) return '';
  return md.render(articleStore.currentArticle.summary);
});

// 计算属性：分割来源 URL
const originUrls = computed(() => {
  const urlString = articleStore.currentArticle?.origin_url;
  if (!urlString) return [];
  const urlPattern = /(https:\/\/[\w\-]+(\.[\w\-]+)+([\w\-.,@?^=%&:/~+#]*[\w\-@?^=%&/~+#]))/g;
  return urlString.match(urlPattern) || [];
});

// 加载某篇新闻的官方解读列表
const fetchInterpretations = async () => {
  if (!articleStore.currentArticle || articleStore.currentArticle.type !== 'news') return;
  interpretationsLoading.value = true;
  try {
    interpretations.value = await articleApi.getInterpretations(articleId.value);
  } catch (e) {
    interpretations.value = [];
  } finally {
    interpretationsLoading.value = false;
  }
};

// 根据当前路由加载文章数据（路由变化时需重新执行，否则内容不刷新）
async function loadArticleData() {
  const id = articleId.value;
  if (!id) return;
  stopSpeech();
  await articleStore.fetchArticle(id);
  await checkFavoriteStatus();
  if (articleStore.currentArticle?.type === 'news') {
    await articleStore.fetchCategories();
    await fetchInterpretations();
  } else {
    interpretations.value = [];
  }
}

onMounted(loadArticleData);

// 同一组件复用时（如从 /articles/6 点进 /articles/16），路由变了但组件未销毁，需监听并重新拉取
watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId && newId !== oldId) loadArticleData();
  }
);

// 组件销毁前停止播报
onBeforeUnmount(() => {
  stopSpeech();
});

// --- 语音播报逻辑 START ---

// 辅助函数：去除 HTML 标签，提取纯文本
const stripHtml = (html: string) => {
  const tmp = document.createElement('DIV');
  tmp.innerHTML = html;
  return tmp.textContent || tmp.innerText || '';
};

const handleSpeech = () => {
  if (!articleStore.currentArticle) return;

  // 1. 如果已经在播放流程中
  if (isSpeaking.value) {
    if (isPaused.value) {
      // 当前是暂停，点击继续
      synth.resume();
      isPaused.value = false;
      ElMessage.info('继续播放');
    } else {
      // 当前是播放，点击暂停
      synth.pause();
      isPaused.value = true;
      ElMessage.info('已暂停');
    }
    return;
  }

  // 2. 开始新的播放
  // 拼接朗读文本：标题 + 摘要 + 正文
  const titleText = articleStore.currentArticle.title;
  const summaryText = renderedSummary.value ? `摘要：${stripHtml(renderedSummary.value)}。` : '';
  // 注意：这里读取的是 renderedContent（HTML），通过 stripHtml 转为纯文本，避免朗读 Markdown 符号
  const contentText = `正文：${stripHtml(renderedContent.value)}`;
  
  const fullText = `${titleText}。${summaryText}${contentText}`;

  utterance = new SpeechSynthesisUtterance(fullText);
  utterance.lang = 'zh-CN'; // 设置为中文
  utterance.rate = 1;       // 语速正常
  utterance.pitch = 1;      // 音调正常

  // 播放结束时的回调
  utterance.onend = () => {
    isSpeaking.value = false;
    isPaused.value = false;
    utterance = null;
  };

  // 播放出错时的回调
  utterance.onerror = (e) => {
    console.error('语音播放出错', e);
    isSpeaking.value = false;
    isPaused.value = false;
  };

  // 停止之前的播放并开始新的
  synth.cancel();
  synth.speak(utterance);
  isSpeaking.value = true;
  isPaused.value = false;
  ElMessage.success('开始语音播报');
};

const stopSpeech = () => {
  if (synth.speaking || synth.pending) {
    synth.cancel();
  }
  isSpeaking.value = false;
  isPaused.value = false;
  utterance = null;
};
// --- 语音播报逻辑 END ---

// 检查收藏状态
const checkFavoriteStatus = async () => {
  try {
    const response = await favoriteApi.checkFavorite(articleId.value);
    isFavorite.value = response.is_favorite;
  } catch (error) {
    console.error('检查收藏状态失败:', error);
  }
};

// 处理收藏
const handleFavorite = async () => {
  loading.value = true;
  try {
    if (isFavorite.value) {
      await favoriteApi.removeFavorite(articleId.value);
      isFavorite.value = false;
      ElMessage.success('取消收藏成功');
    } else {
      await favoriteApi.addFavorite(articleId.value);
      isFavorite.value = true;
      ElMessage.success('收藏成功');
    }
  } catch (error) {
    ElMessage.error('收藏操作失败，请重试');
  } finally {
    loading.value = false;
  }
};

const openEditor = () => { showEditor.value = true; };
const closeEditor = () => { showEditor.value = false; };
const handleSaveArticle = async () => { await articleStore.fetchArticle(articleId.value); };

// 打开/关闭「添加官方解读」弹窗
const openAddInterpretation = () => {
  addInterpTitle.value = '';
  addInterpSummary.value = '';
  addInterpContent.value = '';
  addInterpCategoryId.value = articleStore.currentArticle?.category_id ?? null;
  showAiGenerateBox.value = false;
  aiGenerateContent.value = '';
  aiGenerateError.value = '';
  showAddInterpretationModal.value = true;
};
const closeAddInterpretation = () => {
  showAddInterpretationModal.value = false;
  showAiGenerateBox.value = false;
  aiGenerateLoading.value = false;
};

// 解析 AI 生成的结构化内容：##TITLE## ... ##SUMMARY## ... ##BODY## ...
function parseAiGenerated(raw: string): { title: string; summary: string; body: string } {
  const parts = raw.split(/##(?:TITLE|SUMMARY|BODY)##/);
  // 顺序为 [前缀, title, summary, body]，共 4 段
  if (parts.length >= 4) {
    return {
      title: (parts[1] ?? '').trim(),
      summary: (parts[2] ?? '').trim(),
      body: (parts[3] ?? '').trim()
    };
  }
  if (parts.length >= 2) {
    return { title: '', summary: '', body: parts.slice(1).join('').trim() || raw.trim() };
  }
  return { title: '', summary: '', body: raw.trim() };
}

const startAiGenerate = async () => {
  showAiGenerateBox.value = true;
  aiGenerateContent.value = '';
  aiGenerateError.value = '';
  aiGenerateLoading.value = true;
  try {
    await articleApi.generateInterpretationStream(
      articleId.value,
      (chunk) => {
        aiGenerateContent.value += chunk;
        nextTick(() => {
          aiGenerateContentRef.value?.scrollTo?.({ top: (aiGenerateContentRef.value?.scrollHeight ?? 0), behavior: 'smooth' });
        });
      },
      () => {
        aiGenerateLoading.value = false;
        const parsed = parseAiGenerated(aiGenerateContent.value);
        if (parsed.body) {
          addInterpContent.value = parsed.body;
          if (parsed.title) addInterpTitle.value = parsed.title;
          if (parsed.summary) addInterpSummary.value = parsed.summary;
        }
      }
    );
  } catch (e) {
    aiGenerateError.value = e instanceof Error ? e.message : 'AI 生成失败';
    aiGenerateLoading.value = false;
  }
};

const fillContentAndCloseAiBox = () => {
  const parsed = parseAiGenerated(aiGenerateContent.value);
  if (parsed.body) addInterpContent.value = parsed.body;
  if (parsed.title) addInterpTitle.value = parsed.title;
  if (parsed.summary) addInterpSummary.value = parsed.summary;
  showAiGenerateBox.value = false;
  ElMessage.success('已填入标题、摘要与正文，可继续编辑或提交');
};

// 提交添加官方解读
const submitAddInterpretation = async () => {
  if (!addInterpTitle.value.trim()) {
    ElMessage.warning('请输入解读标题');
    return;
  }
  if (!addInterpContent.value.trim()) {
    ElMessage.warning('请输入解读内容');
    return;
  }
  const cid = addInterpCategoryId.value ?? articleStore.currentArticle?.category_id;
  if (cid == null) {
    ElMessage.warning('请选择分类');
    return;
  }
  addInterpSubmitting.value = true;
  try {
    await articleApi.addInterpretation(articleId.value, {
      title: addInterpTitle.value.trim(),
      summary: addInterpSummary.value.trim() || undefined,
      content: addInterpContent.value.trim(),
      category_id: cid
    });
    ElMessage.success('官方解读已添加');
    closeAddInterpretation();
    await fetchInterpretations();
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '添加失败，请重试');
  } finally {
    addInterpSubmitting.value = false;
  }
};

</script>

<template>
  <div class="article-detail-container">
    <div v-if="articleStore.currentArticle" class="article-detail">
      <!-- 头部区域 -->
      <div class="article-header">
        <div class="article-meta">
          <span class="category">{{ articleStore.currentArticle.category?.name || '未知分类' }}</span>
          <span class="type">{{ articleStore.currentArticle.type === 'news' ? '新闻' : '解读' }}</span>
          <span class="date">{{ new Date(articleStore.currentArticle.publish_date).toLocaleDateString() }}</span>
        </div>
        
        <h1 class="article-title">{{ articleStore.currentArticle.title }}</h1>
        
        <div class="article-info">
          <span class="source">来源：{{ articleStore.currentArticle.source_name }}</span>
          <span class="views">阅读量：{{ articleStore.currentArticle.view_count }}</span>
        </div>
        
        <!-- 摘要区域 -->
        <div v-if="articleStore.currentArticle.summary" class="article-summary">
          <h3>摘要</h3>
          <div class="summary-content markdown-body" v-html="renderedSummary"></div>
        </div>
      </div>
      
      <!-- 封面图 -->
      <div v-if="articleStore.currentArticle.cover_image" class="article-cover">
        <img :src="articleStore.currentArticle.cover_image" :alt="articleStore.currentArticle.title" />
      </div>
      
      <!-- 正文区域 -->
      <div class="article-content markdown-body" v-html="renderedContent"></div>
      
      <!-- 来源链接 -->
      <div v-if="originUrls.length > 0" class="article-origins">
        <h3>来源链接</h3>
        <ul class="origin-urls">
          <li v-for="(url, index) in originUrls" :key="index">
            <a :href="url" target="_blank" rel="noopener noreferrer">{{ url }}</a>
          </li>
        </ul>
      </div>

      <!-- 官方解读（仅新闻显示；所有人可查看，管理员可添加） -->
      <div v-if="isNews" class="article-interpretations">
        <h3><el-icon><Document /></el-icon> 官方解读</h3>
        <p v-if="interpretationsLoading" class="interp-loading">加载中...</p>
        <template v-else>
          <ul v-if="interpretations.length > 0" class="interpretation-list">
            <li v-for="item in interpretations" :key="item.id" class="interpretation-item">
              <router-link :to="`/articles/${item.id}`" class="interpretation-link">
                <span class="interp-title">{{ item.title }}</span>
                <span class="interp-date">{{ new Date(item.publish_date).toLocaleDateString() }}</span>
              </router-link>
            </li>
          </ul>
          <p v-else class="interp-empty">暂无官方解读</p>
          <el-button v-if="isAdmin" type="primary" @click.stop="openAddInterpretation" size="default" round class="add-interp-btn">
            <el-icon><Plus /></el-icon> 添加官方解读
          </el-button>
        </template>
      </div>
      
      <!-- 底部操作栏 -->
      <div class="article-footer">
        <!-- 语音播报按钮 -->
        <el-button 
          :type="isSpeaking && !isPaused ? 'warning' : 'primary'" 
          @click="handleSpeech"
          size="large"
          round
          plain
        >
          <el-icon v-if="isSpeaking && !isPaused"><VideoPause /></el-icon>
          <el-icon v-else><VideoPlay /></el-icon>
          <span style="margin-left: 6px">{{ isSpeaking ? (isPaused ? '继续播放' : '暂停播放') : '听文章' }}</span>
        </el-button>

        <el-button 
          :type="isFavorite ? 'success' : 'danger'" 
          @click="handleFavorite"
          :loading="loading"
          size="large"
          round
        >
          <el-icon v-if="!isFavorite"><Star /></el-icon>
          <el-icon v-else><StarFilled /></el-icon>
          {{ isFavorite ? '取消收藏' : '收藏文章' }}
        </el-button>
        
        <el-button v-if="isAdmin" type="primary" @click="openEditor" size="large" round plain>
          <el-icon><EditPen /></el-icon> 编辑
        </el-button>
        
        <el-button type="info" @click="router.back()" size="large" round plain>
          <el-icon><Back /></el-icon> 返回
        </el-button>
      </div>
      
      <!-- 编辑弹窗 -->
      <ArticleEditor 
        :article-id="articleId" 
        :visible="showEditor" 
        @close="closeEditor"
        @save="handleSaveArticle"
      />

      <!-- 添加官方解读弹窗 -->
      <el-dialog
        v-model="showAddInterpretationModal"
        title="添加官方解读"
        width="560px"
        :close-on-click-modal="false"
        @close="closeAddInterpretation"
      >
        <el-form label-width="80px">
          <el-form-item label="标题" required>
            <el-input v-model="addInterpTitle" placeholder="解读标题" maxlength="255" show-word-limit />
          </el-form-item>
          <el-form-item label="摘要">
            <el-input v-model="addInterpSummary" type="textarea" :rows="2" placeholder="选填，列表页展示" />
          </el-form-item>
          <el-form-item label="分类" required>
            <el-select v-model="addInterpCategoryId" placeholder="选择分类" style="width: 100%">
              <el-option
                v-for="c in articleStore.categories"
                :key="c.id"
                :label="c.name"
                :value="c.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="正文" required>
            <div class="ai-fill-row">
              <el-button
                type="success"
                plain
                :loading="aiGenerateLoading"
                :disabled="aiGenerateLoading"
                @click="startAiGenerate"
              >
                {{ aiGenerateLoading ? 'AI 生成中…' : 'AI 填补内容' }}
              </el-button>
            </div>
            <!-- AI 流式生成展示区 -->
            <div v-if="showAiGenerateBox" class="ai-generate-box">
              <div class="ai-generate-title">AI 生成内容（流式输出）</div>
              <div ref="aiGenerateContentRef" class="ai-generate-content">
                <span class="ai-generate-text">{{ aiGenerateContent }}</span>
                <span v-if="aiGenerateLoading" class="ai-generate-cursor">|</span>
              </div>
              <p v-if="aiGenerateError" class="ai-generate-error">{{ aiGenerateError }}</p>
              <el-button
                v-if="!aiGenerateLoading"
                type="primary"
                size="small"
                class="ai-fill-btn"
                @click="fillContentAndCloseAiBox"
              >
                填入正文并关闭
              </el-button>
            </div>
            <el-input v-model="addInterpContent" type="textarea" :rows="10" placeholder="解读正文（支持 Markdown）；可使用上方「AI 填补内容」自动生成" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="closeAddInterpretation">取消</el-button>
          <el-button type="primary" :loading="addInterpSubmitting" @click="submitAddInterpretation">提交</el-button>
        </template>
      </el-dialog>
    </div>
    
    <!-- 加载与错误状态 -->
    <div v-else-if="articleStore.loading" class="loading-state">
      <div class="spinner"></div>
      <p>正在加载文章详情...</p>
    </div>
    
    <div v-else class="error-state">
      <p>文章不存在或已被删除</p>
      <el-button @click="router.back()">返回列表</el-button>
    </div>
  </div>
</template>

<style scoped>
/* ================= 基础布局 ================= */
.article-detail-container {
  max-width: 960px;
  margin: 0 auto;
  padding: 50px 30px;
  min-height: calc(100vh - 70px);
  background: white;
  box-shadow: 0 0 60px rgba(0, 0, 0, 0.03);
}

/* ================= 头部样式 ================= */
.article-header {
  margin-bottom: 40px;
  animation: fadeInDown 0.6s ease-out;
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.article-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  font-size: 13px;
  flex-wrap: wrap;
}

.category {
  background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
  color: #667eea;
  padding: 6px 16px;
  border-radius: 20px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.15);
  transition: all 0.3s ease;
}

.category:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.25);
}

.type {
  background: linear-gradient(135deg, #d1fae5, #a7f3d0);
  color: #059669;
  padding: 6px 16px;
  border-radius: 20px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(5, 150, 105, 0.15);
  transition: all 0.3s ease;
}

.type:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(5, 150, 105, 0.25);
}

.date {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #d97706;
  padding: 6px 16px;
  border-radius: 20px;
  font-weight: 600;
  margin-left: auto;
  box-shadow: 0 2px 8px rgba(217, 119, 6, 0.15);
}

.article-title {
  font-size: 42px;
  font-weight: 800;
  color: #1a1a1a;
  line-height: 1.3;
  margin: 0 0 24px 0;
  letter-spacing: -1px;
  background: linear-gradient(135deg, #1a1a1a, #4a5568);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.article-info {
  display: flex;
  gap: 32px;
  font-size: 14px;
  color: #6b7280;
  padding-bottom: 24px;
  border-bottom: 2px solid rgba(102, 126, 234, 0.1);
  font-weight: 500;
}

.article-info span {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ================= 摘要样式 (美化) ================= */
.article-summary {
  margin-top: 30px;
  padding: 24px 28px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
  border-left: 4px solid #667eea;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.1);
  position: relative;
  overflow: hidden;
}

.article-summary::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 100px;
  height: 100px;
  background: radial-gradient(circle, rgba(102, 126, 234, 0.1) 0%, transparent 70%);
  border-radius: 50%;
}

.article-summary h3 {
  font-size: 18px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0 0 14px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.article-summary h3::before {
  content: "📝";
  font-size: 20px;
}

.summary-content :deep(p) {
  margin: 0;
  font-size: 16px;
  line-height: 1.7;
  color: #4a5568;
  position: relative;
  z-index: 1;
}

/* ================= 封面图 ================= */
.article-cover {
  margin: 40px 0;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
  transition: transform 0.3s ease;
}

.article-cover:hover {
  transform: scale(1.01);
}

.article-cover img {
  width: 100%;
  height: auto;
  display: block;
  transition: transform 0.5s ease;
}

/* ================= 正文 Markdown 美化 ================= */
.article-content {
  margin-bottom: 80px;
  color: #2c3e50;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
  font-size: 18px;
  line-height: 1.9;
  word-wrap: break-word;
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

.markdown-body :deep(p) {
  margin-bottom: 1.8em;
  text-align: justify;
  color: #374151;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  color: #111827;
  font-weight: 800;
  margin-top: 2.5em;
  margin-bottom: 1.2em;
  line-height: 1.4;
}

.markdown-body :deep(h1) {
  font-size: 2.25em;
  border-bottom: 3px solid rgba(102, 126, 234, 0.2);
  padding-bottom: 0.4em;
  position: relative;
}

.markdown-body :deep(h2) {
  font-size: 1.88em;
  border-bottom: 2px solid rgba(102, 126, 234, 0.15);
  padding-bottom: 0.4em;
}

.markdown-body :deep(h3) {
  font-size: 1.5em;
  position: relative;
  padding-left: 20px;
}

.markdown-body :deep(h3)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 5px;
  background: linear-gradient(180deg, #667eea, #764ba2);
  border-radius: 3px;
}

.markdown-body :deep(h4) {
  font-size: 1.25em;
  color: #4a5568;
}

.markdown-body :deep(strong) {
  color: #667eea;
  font-weight: 700;
  background: linear-gradient(180deg, transparent 70%, rgba(102, 126, 234, 0.15) 70%);
  padding: 0 3px;
  border-radius: 3px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 2em;
  margin-bottom: 1.8em;
}

.markdown-body :deep(li) {
  margin-bottom: 0.7em;
  line-height: 1.8;
}

.markdown-body :deep(blockquote) {
  margin: 2em 0;
  padding: 16px 24px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
  border-left: 5px solid #667eea;
  color: #4a5568;
  font-style: italic;
  border-radius: 8px;
  font-size: 17px;
}

.markdown-body :deep(pre) {
  background: linear-gradient(135deg, #282c34, #21252b);
  color: #abb2bf;
  padding: 20px;
  border-radius: 12px;
  overflow-x: auto;
  margin-bottom: 2em;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.markdown-body :deep(code) {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 0.9em;
  font-weight: 600;
}

.markdown-body :deep(a) {
  color: #667eea;
  text-decoration: none;
  border-bottom: 2px solid transparent;
  transition: all 0.3s ease;
  font-weight: 600;
}

.markdown-body :deep(a:hover) {
  border-bottom-color: #667eea;
  color: #764ba2;
}

/* ================= 来源链接 ================= */
.article-origins {
  margin: 50px 0;
  padding: 28px 32px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
  border-radius: 16px;
  border: 2px solid rgba(102, 126, 234, 0.1);
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.08);
}

.article-origins h3 {
  font-size: 20px;
  margin: 0 0 20px 0;
  color: #2c3e50;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}

.article-origins h3::before {
  content: '🔗';
  font-size: 22px;
}

.origin-urls {
  list-style: none;
  padding: 0;
  margin: 0;
}

.origin-urls li {
  margin-bottom: 14px;
  display: flex;
  align-items: flex-start;
  padding: 12px 16px;
  background: white;
  border-radius: 10px;
  transition: all 0.3s ease;
  border: 1px solid rgba(102, 126, 234, 0.1);
}

.origin-urls li:hover {
  transform: translateX(5px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
  border-color: rgba(102, 126, 234, 0.3);
}

.origin-urls li::before {
  content: '🔗';
  margin-right: 12px;
  font-size: 14px;
  margin-top: 2px;
  flex-shrink: 0;
}

.origin-urls a {
  color: #4a5568;
  text-decoration: none;
  word-break: break-all;
  font-size: 14px;
  line-height: 1.6;
  transition: color 0.3s ease;
  font-weight: 500;
}

.origin-urls a:hover {
  color: #667eea;
}

/* ================= 官方解读 ================= */
.article-interpretations {
  margin: 50px 0;
  padding: 28px 32px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
  border-radius: 16px;
  border: 2px solid rgba(102, 126, 234, 0.1);
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.08);
}

.article-interpretations h3 {
  font-size: 20px;
  margin: 0 0 20px 0;
  color: #2c3e50;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}

.interpretation-list {
  list-style: none;
  padding: 0;
  margin: 0 0 16px 0;
}

.interpretation-item {
  margin-bottom: 10px;
  border-radius: 10px;
  border: 1px solid rgba(102, 126, 234, 0.1);
  transition: all 0.25s ease;
  list-style: none;
}

.interpretation-item:hover {
  border-color: rgba(102, 126, 234, 0.35);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.12);
}

.interpretation-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: white;
  border-radius: 10px;
  text-decoration: none;
  color: inherit;
  cursor: pointer;
  width: 100%;
  box-sizing: border-box;
}

.interpretation-link:hover {
  color: inherit;
}

.interp-title {
  font-weight: 600;
  color: #2c3e50;
}

.interpretation-link:hover .interp-title {
  color: #667eea;
}

.interp-date {
  font-size: 13px;
  color: #6b7280;
}

.interp-loading,
.interp-empty {
  color: #6b7280;
  margin: 12px 0;
}

.add-interp-btn {
  margin-top: 8px;
}

/* ================= 添加解读弹窗内 AI 填补 ================= */
.ai-fill-row {
  margin-bottom: 12px;
}

.ai-generate-box {
  margin-bottom: 12px;
  padding: 12px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.06), rgba(118, 75, 162, 0.06));
  border: 1px solid rgba(102, 126, 234, 0.2);
  border-radius: 12px;
}

.ai-generate-title {
  font-size: 13px;
  color: #667eea;
  margin-bottom: 8px;
  font-weight: 600;
}

.ai-generate-content {
  max-height: 220px;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.7;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 8px 0;
}

.ai-generate-cursor {
  display: inline-block;
  animation: ai-cursor-blink 0.8s step-end infinite;
  color: #667eea;
  margin-left: 2px;
}

@keyframes ai-cursor-blink {
  50% { opacity: 0; }
}

.ai-generate-error {
  color: #f56c6c;
  font-size: 13px;
  margin: 8px 0 0 0;
}

.ai-fill-btn {
  margin-top: 10px;
}

/* ================= 底部操作栏 ================= */
.article-footer {
  margin-top: 80px;
  padding: 30px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
  border-radius: 20px;
  border: 2px solid rgba(102, 126, 234, 0.1);
  display: flex;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.1);
}

.article-footer .el-button {
  font-weight: 600;
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.article-footer .el-button:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.25);
}

/* ================= 状态提示 ================= */
.loading-state,
.error-state {
  text-align: center;
  padding: 120px 0;
  color: #6b7280;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 5px solid rgba(102, 126, 234, 0.1);
  border-top: 5px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 24px;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.error-state p {
  font-size: 18px;
  color: #6b7280;
  margin-bottom: 24px;
}

/* ================= 响应式设计 ================= */
@media (max-width: 768px) {
  .article-detail-container {
    padding: 30px 20px;
  }

  .article-title {
    font-size: 32px;
  }

  .article-info {
    flex-direction: column;
    gap: 12px;
  }

  .article-footer {
    padding: 20px;
  }

  .article-footer .el-button {
    width: 100%;
  }
}
</style>