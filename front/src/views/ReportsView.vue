<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useChatStore } from '../stores/chat';
import type { AnalysisReport } from '../types/chat';

const router = useRouter();
const chatStore = useChatStore();

const loading = ref(false);
const error = ref('');
const currentPage = ref(1);
const isArchivedFilter = ref<boolean | null>(null);

// 加载报告列表
onMounted(async () => {
  await fetchReports();
});

// 获取报告列表
const fetchReports = async () => {
  loading.value = true;
  try {
    await chatStore.fetchReports({
      page: currentPage.value,
      page_size: 10,
      is_archived: isArchivedFilter.value || undefined
    });
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取报告列表失败';
  } finally {
    loading.value = false;
  }
};

// 切换归档状态筛选
const toggleArchivedFilter = (isArchived: boolean | null) => {
  isArchivedFilter.value = isArchived;
  currentPage.value = 1;
  fetchReports();
};

// 查看报告详情
const viewReport = (report: AnalysisReport) => {
  // TODO: 实现报告详情查看功能
  console.log('查看报告:', report);
};
</script>

<template>
  <div class="reports-container">
    <div class="reports-header">
      <h2>咨询报告</h2>
      <div class="filter-buttons">
        <button 
          :class="{ active: isArchivedFilter === null }"
          @click="toggleArchivedFilter(null)"
        >
          全部
        </button>
        <button 
          :class="{ active: isArchivedFilter === false }"
          @click="toggleArchivedFilter(false)"
        >
          未归档
        </button>
        <button 
          :class="{ active: isArchivedFilter === true }"
          @click="toggleArchivedFilter(true)"
        >
          已归档
        </button>
      </div>
    </div>
    
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
    
    <div v-if="loading" class="loading">
      加载中...
    </div>
    
    <div v-else-if="chatStore.reports.length === 0" class="empty-reports">
      <h3>暂无报告</h3>
      <p>您还没有生成任何咨询报告</p>
    </div>
    
    <div v-else class="reports-list">
      <div 
        v-for="report in chatStore.reports" 
        :key="report.id"
        class="report-card"
        @click="viewReport(report)"
      >
        <div class="report-header">
          <h3 class="report-title">{{ report.title }}</h3>
          <span v-if="report.is_archived" class="archived-tag">已归档</span>
        </div>
        
        <div class="report-meta">
          <span class="date">{{ new Date(report.created_at).toLocaleDateString() }}</span>
          <span class="article-count">引用 {{ report.reference_article_ids.split(',').length }} 篇文章</span>
        </div>
        
        <div class="report-preview" v-if="report.content">
          <p>{{ report.content.substring(0, 150) }}...</p>
        </div>
        
        <div class="report-footer" v-if="report.user_note">
          <div class="user-note">
            <strong>备注：</strong>{{ report.user_note }}
          </div>
        </div>
      </div>
    </div>
    
    <!-- 分页 -->
    <div class="pagination" v-if="chatStore.reports.length > 0">
      <button 
        @click="currentPage--; fetchReports()" 
        :disabled="currentPage === 1"
      >
        上一页
      </button>
      <span>第 {{ currentPage }} 页</span>
      <button 
        @click="currentPage++; fetchReports()" 
        :disabled="chatStore.reports.length < 10"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<style scoped>
.reports-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

.reports-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.reports-header h2 {
  margin: 0;
  font-size: 24px;
  color: #333;
}

.filter-buttons {
  display: flex;
  gap: 10px;
}

.filter-buttons button {
  padding: 8px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background-color: white;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-buttons button:hover {
  border-color: #409eff;
  color: #409eff;
}

.filter-buttons button.active {
  background-color: #409eff;
  color: white;
  border-color: #409eff;
}

.error-message {
  background-color: #fef0f0;
  color: #f56c6c;
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 20px;
  font-size: 14px;
}

.loading {
  text-align: center;
  padding: 50px;
  color: #666;
  font-size: 16px;
}

.empty-reports {
  text-align: center;
  padding: 50px;
  color: #666;
}

.empty-reports h3 {
  margin: 0 0 10px 0;
  font-size: 20px;
  color: #333;
}

.reports-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.report-card {
  background-color: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.report-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}

.report-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #333;
  flex: 1;
  line-height: 1.4;
}

.archived-tag {
  background-color: #f0f9eb;
  color: #67c23a;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  margin-left: 10px;
}

.report-meta {
  display: flex;
  gap: 15px;
  font-size: 12px;
  color: #999;
  margin-bottom: 15px;
}

.report-preview {
  font-size: 14px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 15px;
  flex: 1;
}

.report-preview p {
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.report-footer {
  margin-top: auto;
  padding-top: 15px;
  border-top: 1px solid #eee;
}

.user-note {
  font-size: 14px;
  color: #666;
  font-style: italic;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  margin-top: 30px;
}

.pagination button {
  padding: 8px 16px;
  border: 1px solid #ddd;
  background-color: white;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.pagination button:hover:not(:disabled) {
  border-color: #409eff;
  color: #409eff;
}

.pagination button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
</style>