<template>
  <div class="personal-page">
    <div class="page-header">
      <h1 class="title"><img src="/emojis/三月七_骄傲.png" class="emoji-icon-lg" /> 个人数据统计</h1>
      <p>查看你的对话偏好和统计数据</p>
    </div>

    <div class="profile-section">
      <div class="profile-card">
        <div class="profile-header">
          <img 
            :src="userProfile.avatar || '/emojis/三月七_暗中观察.png'" 
            alt="avatar" 
            class="profile-avatar"
          />
          <div class="profile-info">
            <h2 class="profile-nickname">{{ userProfile.nickname || userProfile.username }}</h2>
            <span class="profile-username">@{{ userProfile.username }}</span>
            <span class="profile-role">{{ userProfile.role === 'admin' ? '管理员' : '用户' }}</span>
          </div>
          <button class="btn btn-secondary edit-btn" @click="showEditModal = true">
            编辑资料
          </button>
        </div>
      </div>
    </div>

    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>编辑个人资料</h3>
          <button class="modal-close" @click="showEditModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>昵称</label>
            <input 
              v-model="editForm.nickname" 
              type="text" 
              class="form-input"
              placeholder="输入你的昵称"
              maxlength="100"
            />
          </div>
          <div class="form-group">
            <label>头像URL</label>
            <input 
              v-model="editForm.avatar" 
              type="text" 
              class="form-input"
              placeholder="输入头像图片URL"
              maxlength="500"
            />
            <div v-if="editForm.avatar" class="avatar-preview">
              <img :src="editForm.avatar" alt="预览" @error="onAvatarError" />
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showEditModal = false">取消</button>
          <button class="btn btn-primary" @click="saveProfile" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <span class="loading-icon"><img src="/emojis/三月七_开心.png" class="emoji-icon-lg spin" /></span>
      <p>加载中...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <span class="error-icon">❌</span>
      <p>{{ error }}</p>
      <button class="btn btn-primary" @click="fetchStats">重试</button>
    </div>

    <div v-else class="stats-container">
      <div class="summary-cards">
        <div class="summary-card">
          <div class="card-icon"><img src="/emojis/三月七_悄悄话.png" class="emoji-icon" /></div>
          <div class="card-content">
            <span class="card-value">{{ stats.summary?.total_conversations || 0 }}</span>
            <span class="card-label">总对话数</span>
          </div>
        </div>
        <div class="summary-card">
          <div class="card-icon"><img src="/emojis/三月七_点赞.png" class="emoji-icon" /></div>
          <div class="card-content">
            <span class="card-value">{{ stats.summary?.avg_rating || 0 }}</span>
            <span class="card-label">平均评分</span>
          </div>
        </div>
        <div class="summary-card">
          <div class="card-icon"><img src="/emojis/三月七_点赞.png" class="emoji-icon" /></div>
          <div class="card-content">
            <span class="card-value">{{ positiveCount }}</span>
            <span class="card-label">正面关键词</span>
          </div>
        </div>
        <div class="summary-card">
          <div class="card-icon"><img src="/emojis/三月七_无语.png" class="emoji-icon" /></div>
          <div class="card-content">
            <span class="card-value">{{ negativeCount }}</span>
            <span class="card-label">负面关键词</span>
          </div>
        </div>
      </div>

      <div class="charts-grid">
        <div class="chart-card">
          <h3 class="chart-title"><img src="/emojis/三月七_骄傲.png" class="emoji-icon" /> 对话趋势（近30天）</h3>
          <div v-if="hasConversationTrend" ref="trendChartRef" class="chart-container"></div>
          <div v-else class="no-data">暂无数据</div>
        </div>

        <div class="chart-card">
          <h3 class="chart-title"><img src="/emojis/三月七_点赞.png" class="emoji-icon" /> 评分分布</h3>
          <div v-if="hasRatingDistribution" ref="ratingChartRef" class="chart-container"></div>
          <div v-else class="no-data">暂无数据</div>
        </div>

        <div class="chart-card">
          <h3 class="chart-title"><img src="/emojis/三月七_暗中观察.png" class="emoji-icon" /> 兴趣关键词</h3>
          <div v-if="hasInterestKeywords" ref="wordCloudChartRef" class="chart-container"></div>
          <div v-else class="no-data">暂无数据</div>
        </div>

        <div class="chart-card">
          <h3 class="chart-title"><img src="/emojis/三月七_开心.png" class="emoji-icon" /> 话题分布</h3>
          <div v-if="hasTopics" ref="topicChartRef" class="chart-container"></div>
          <div v-else class="no-data">暂无数据</div>
        </div>
      </div>

      <div class="keywords-section">
        <div class="keywords-card positive">
          <h3>👍 正面关键词 TOP 5</h3>
          <div v-if="stats.top_positive_keywords?.length" class="keywords-list">
            <span
              v-for="(item, index) in stats.top_positive_keywords"
              :key="index"
              class="keyword-tag positive"
            >
              {{ item.keyword }} ({{ item.count }})
            </span>
          </div>
          <div v-else class="no-data">暂无数据</div>
        </div>
        <div class="keywords-card negative">
          <h3>👎 负面关键词 TOP 5</h3>
          <div v-if="stats.top_negative_keywords?.length" class="keywords-list">
            <span
              v-for="(item, index) in stats.top_negative_keywords"
              :key="index"
              class="keyword-tag negative"
            >
              {{ item.keyword }} ({{ item.count }})
            </span>
          </div>
          <div v-else class="no-data">暂无数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '../utils/api'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const loading = ref(true)
const error = ref(null)
const stats = ref({})

const showEditModal = ref(false)
const saving = ref(false)
const userProfile = ref({
  username: '',
  nickname: '',
  avatar: '',
  role: ''
})
const editForm = ref({
  nickname: '',
  avatar: ''
})

const trendChartRef = ref(null)
const ratingChartRef = ref(null)
const wordCloudChartRef = ref(null)
const topicChartRef = ref(null)

let trendChart = null
let ratingChart = null
let wordCloudChart = null
let topicChart = null

const positiveCount = computed(() => {
  return stats.value.top_positive_keywords?.length || 0
})

const negativeCount = computed(() => {
  return stats.value.top_negative_keywords?.length || 0
})

const hasConversationTrend = computed(() => {
  return stats.value.conversation_trend?.length > 0
})

const hasRatingDistribution = computed(() => {
  const dist = stats.value.rating_distribution
  if (!dist) return false
  return Object.values(dist).some(v => v > 0)
})

const hasInterestKeywords = computed(() => {
  return stats.value.interest_keywords?.length > 0
})

const hasTopics = computed(() => {
  return positiveCount.value > 0 || negativeCount.value > 0
})

async function fetchUserProfile() {
  try {
    const response = await api.get('/user/profile')
    if (response.success) {
      userProfile.value = response.profile
      editForm.value = {
        nickname: response.profile.nickname || response.profile.username,
        avatar: response.profile.avatar || ''
      }
    }
  } catch (e) {
    console.error('获取用户信息失败:', e)
  }
}

async function saveProfile() {
  saving.value = true
  try {
    const response = await api.put('/user/profile', {
      nickname: editForm.value.nickname,
      avatar: editForm.value.avatar
    })
    if (response.success) {
      userProfile.value.nickname = editForm.value.nickname
      userProfile.value.avatar = editForm.value.avatar
      showEditModal.value = false
    }
  } catch (e) {
    console.error('保存失败:', e)
  } finally {
    saving.value = false
  }
}

function onAvatarError(e) {
  e.target.style.display = 'none'
}

async function fetchStats() {
  loading.value = true
  error.value = null

  try {
    const response = await api.get('/user/preference/stats')
    if (response.success) {
      stats.value = response.stats
    } else {
      error.value = '获取统计数据失败'
    }
  } catch (e) {
    error.value = e.message || '获取统计数据失败'
  } finally {
    loading.value = false
  }
}

function initTrendChart() {
  if (!trendChartRef.value || !hasConversationTrend.value) return

  const dates = stats.value.conversation_trend.map(item => item.date)
  const counts = stats.value.conversation_trend.map(item => item.count)

  trendChart = echarts.init(trendChartRef.value)
  trendChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(30, 30, 46, 0.9)',
      borderColor: '#E94560',
      textStyle: { color: '#fff' }
    },
    grid: {
      left: '10%',
      right: '5%',
      top: '10%',
      bottom: '20%'
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#E94560' } },
      axisLabel: { color: '#aaa', rotate: 45 }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#E94560' } },
      axisLabel: { color: '#aaa' },
      splitLine: { lineStyle: { color: 'rgba(233, 69, 96, 0.2)' } }
    },
    series: [{
      type: 'line',
      data: counts,
      smooth: true,
      lineStyle: { color: '#E94560', width: 3 },
      itemStyle: { color: '#E94560' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(233, 69, 96, 0.4)' },
          { offset: 1, color: 'rgba(233, 69, 96, 0.05)' }
        ])
      }
    }]
  })
}

function initRatingChart() {
  if (!ratingChartRef.value || !hasRatingDistribution.value) return

  const dist = stats.value.rating_distribution
  const data = [
    { value: dist[1], name: '1星' },
    { value: dist[2], name: '2星' },
    { value: dist[3], name: '3星' },
    { value: dist[4], name: '4星' },
    { value: dist[5], name: '5星' }
  ]

  ratingChart = echarts.init(ratingChartRef.value)
  ratingChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(30, 30, 46, 0.9)',
      borderColor: '#E94560',
      textStyle: { color: '#fff' }
    },
    legend: {
      bottom: '2%',
      textStyle: { color: '#aaa', fontSize: 12 },
      itemGap: 12,
      itemWidth: 12,
      itemHeight: 12
    },
    series: [{
      type: 'pie',
      radius: ['30%', '50%'],
      center: ['50%', '40%'],
      avoidLabelOverlap: true,
      label: {
        show: false
      },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold', color: '#fff' }
      },
      data: data,
      color: ['#ff6b6b', '#ffa502', '#ffd93d', '#6bcb77', '#4d96ff']
    }]
  })
}

function initWordCloudChart() {
  if (!wordCloudChartRef.value || !hasInterestKeywords.value) return

  const words = stats.value.interest_keywords.map((item, index) => ({
    name: item.keyword,
    value: Math.max(item.count * 10, 50) + index * 5
  }))

  wordCloudChart = echarts.init(wordCloudChartRef.value)
  wordCloudChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      show: true,
      backgroundColor: 'rgba(30, 30, 46, 0.9)',
      borderColor: '#E94560',
      textStyle: { color: '#fff' }
    },
    series: [{
      type: 'wordCloud',
      shape: 'circle',
      left: 'center',
      top: 'center',
      width: '90%',
      height: '90%',
      sizeRange: [16, 50],
      rotationRange: [-45, 45],
      rotationStep: 15,
      gridSize: 8,
      drawOutOfBound: false,
      textStyle: {
        fontFamily: 'sans-serif',
        fontWeight: 'bold',
        color: function() {
          const colors = ['#E94560', '#FF6B9D', '#C44569', '#FFC75F', '#FF9F1C', '#2EC4B6']
          return colors[Math.floor(Math.random() * colors.length)]
        }
      },
      data: words
    }]
  })
}

function initTopicChart() {
  if (!topicChartRef.value || !hasTopics.value) return

  const positiveData = stats.value.top_positive_keywords?.slice(0, 5).map(item => ({
    name: item.keyword,
    value: item.count,
    itemStyle: { color: '#6bcb77' }
  })) || []

  const negativeData = stats.value.top_negative_keywords?.slice(0, 5).map(item => ({
    name: item.keyword,
    value: item.count,
    itemStyle: { color: '#ff6b6b' }
  })) || []

  const data = [...positiveData, ...negativeData]

  topicChart = echarts.init(topicChartRef.value)
  topicChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(30, 30, 46, 0.9)',
      borderColor: '#E94560',
      textStyle: { color: '#fff' }
    },
    legend: {
      bottom: '2%',
      textStyle: { color: '#aaa' }
    },
    series: [{
      type: 'pie',
      radius: '60%',
      center: ['50%', '42%'],
      data: data,
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      },
      label: {
        color: '#fff',
        formatter: '{b}'
      }
    }]
  })
}

function initCharts() {
  nextTick(() => {
    initTrendChart()
    initRatingChart()
    initWordCloudChart()
    initTopicChart()
  })
}

function handleResize() {
  trendChart?.resize()
  ratingChart?.resize()
  wordCloudChart?.resize()
  topicChart?.resize()
}

onMounted(async () => {
  await fetchUserProfile()
  await fetchStats()
  if (!loading.value && !error.value) {
    initCharts()
  }
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  ratingChart?.dispose()
  wordCloudChart?.dispose()
  topicChart?.dispose()
})
</script>

<style scoped>
.emoji-icon {
  width: 20px;
  height: 20px;
  object-fit: contain;
  vertical-align: middle;
  display: inline-block;
}
.emoji-icon-lg {
  width: 28px;
  height: 28px;
  object-fit: contain;
  vertical-align: middle;
  display: inline-block;
}
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.loading-icon .emoji-icon-lg {
  width: 48px;
  height: 48px;
}
.personal-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow-y: auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-header p {
  color: var(--text-secondary);
  margin-top: 8px;
}

.loading-state,
.error-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.loading-icon,
.error-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-state .btn {
  margin-top: 16px;
}

.stats-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  transition: all 0.3s ease;
}

.summary-card:hover {
  background: rgba(255, 255, 255, 0.08);
  transform: translateY(-2px);
}

.card-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.3) 0%, rgba(255, 107, 157, 0.2) 100%);
  border-radius: 12px;
  font-size: 28px;
}

.card-content {
  display: flex;
  flex-direction: column;
}

.card-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.card-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

@media (max-width: 1200px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 20px;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.chart-container {
  width: 100%;
  height: 250px;
}

.no-data {
  height: 250px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 14px;
}

.keywords-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

@media (max-width: 900px) {
  .keywords-section {
    grid-template-columns: 1fr;
  }
}

.keywords-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 20px;
}

.keywords-card h3 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 16px;
}

.keywords-card.positive h3 {
  color: #6bcb77;
}

.keywords-card.negative h3 {
  color: #ff6b6b;
}

.keywords-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.keyword-tag {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
}

.keyword-tag.positive {
  background: rgba(107, 203, 119, 0.2);
  color: #6bcb77;
  border: 1px solid rgba(107, 203, 119, 0.4);
}

.keyword-tag.negative {
  background: rgba(255, 107, 107, 0.2);
  color: #ff6b6b;
  border: 1px solid rgba(255, 107, 107, 0.4);
}

.profile-section {
  margin-bottom: 24px;
}

.profile-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 24px;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 20px;
}

.profile-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  object-fit: cover;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 4px;
}

.profile-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.profile-nickname {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.profile-username {
  color: var(--text-secondary);
  font-size: 14px;
}

.profile-role {
  color: var(--accent-secondary);
  font-size: 13px;
  background: rgba(233, 69, 96, 0.2);
  padding: 2px 10px;
  border-radius: 10px;
  width: fit-content;
}

.edit-btn {
  flex-shrink: 0;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: linear-gradient(135deg, rgba(26, 26, 46, 0.98) 0%, rgba(22, 33, 62, 0.98) 100%);
  border: 1px solid var(--accent-primary);
  border-radius: 16px;
  width: 90%;
  max-width: 480px;
  box-shadow: 0 20px 60px rgba(233, 69, 96, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  color: var(--text-primary);
  font-size: 18px;
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.modal-close:hover {
  color: var(--accent-primary);
}

.modal-body {
  padding: 24px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 8px;
}

.form-input {
  width: 100%;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 15px;
  transition: all 0.3s ease;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent-primary);
  background: rgba(255, 255, 255, 0.08);
}

.form-input::placeholder {
  color: var(--text-secondary);
}

.avatar-preview {
  margin-top: 12px;
  text-align: center;
}

.avatar-preview img {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--accent-primary);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid var(--border-color);
}
</style>
