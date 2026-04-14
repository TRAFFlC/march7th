<template>
  <div class="main-layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <img src="/emojis/三月七_开心.png" alt="logo" class="logo-img" />
        <h2>七音盒Music7ox</h2>
        <p>角色语音对话系统</p>
      </div>

      <div class="user-info">
        <img :src="userAvatar" alt="avatar" class="user-avatar-img" />
        <div class="user-details">
          <span class="username">{{ userNickname }}</span>
        </div>
      </div>

      <nav class="nav-menu">
        <router-link 
          v-for="item in navItems" 
          :key="item.path"
          :to="item.path"
          class="nav-item"
        >
          <img :src="item.emoji" :alt="item.label" class="nav-emoji" />
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <button class="btn btn-secondary logout-btn" @click="handleLogout">
          退出登录
        </button>
      </div>

      <div class="system-status">
        <div class="status-item">
          <span class="status-label">LLM</span>
          <span :class="['status-value', status.llmActive ? 'active' : '']">
            {{ status.llmActive ? '运行中' : '已停止' }}
          </span>
        </div>
        <div class="status-item">
          <span class="status-label">TTS</span>
          <span :class="['status-value', status.ttsActive ? 'active' : '']">
            {{ status.ttsActive ? '运行中' : '已停止' }}
          </span>
        </div>
        <div class="status-item">
          <span class="status-label">GPU</span>
          <span class="status-value">{{ status.gpuMemoryMb > 0 ? status.gpuMemoryMb + 'MB' : 'N/A' }}</span>
        </div>
      </div>
    </aside>

    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../utils/api'

const authStore = useAuthStore()

const userProfile = ref({
  nickname: '',
  avatar: ''
})

const userNickname = computed(() => {
  return userProfile.value.nickname || authStore.user?.username || '用户'
})

const userAvatar = computed(() => {
  return userProfile.value.avatar || '/emojis/三月七_暗中观察.png'
})

const navItems = [
  { path: '/', emoji: '/emojis/三月七_悄悄话.png', label: '全流程对话' },
  { path: '/llm', emoji: '/emojis/三月七_吃糖.png', label: 'LLM测试' },
  { path: '/tts', emoji: '/emojis/三月七_biu.png', label: 'TTS测试' },
  { path: '/rag', emoji: '/emojis/三月七_暗中观察.png', label: 'RAG管理' },
  { path: '/characters', emoji: '/emojis/三月七_买买买.png', label: '角色管理' },
  { path: '/personal', emoji: '/emojis/三月七_点赞.png', label: '个人数据' },
  { path: '/settings', emoji: '/emojis/三月七_骄傲.png', label: '系统设置' },
  { path: '/debug', emoji: '/emojis/三月七_吃糖.png', label: '调试面板' },
]

const status = ref({
  llmActive: false,
  ttsActive: false,
  gpuMemoryMb: 0
})

async function handleLogout() {
  await authStore.logout()
  await authStore.autoLogin()
}

async function fetchStatus() {
  try {
    const response = await api.get('/system/status')
    if (response.success) {
      status.value = response.status
    }
  } catch (e) {
    console.error('Failed to fetch status:', e)
  }
}

async function fetchUserProfile() {
  try {
    const response = await api.get('/user/profile')
    if (response.success) {
      userProfile.value = {
        nickname: response.profile.nickname || '',
        avatar: response.profile.avatar || ''
      }
    }
  } catch (e) {
    console.error('Failed to fetch user profile:', e)
  }
}

onMounted(async () => {
  if (!authStore.isLoggedIn) {
    await authStore.autoLogin()
  }
  fetchStatus()
  fetchUserProfile()
  setInterval(fetchStatus, 10000)
})
</script>

<style scoped>
.main-layout {
  display: flex;
  width: 100%;
  height: 100%;
}

.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100%;
  background: linear-gradient(180deg, rgba(26, 26, 46, 0.95) 0%, rgba(22, 33, 62, 0.95) 100%);
  border-right: 2px solid var(--accent-primary);
  display: flex;
  flex-direction: column;
  padding: 20px 16px;
  box-shadow: 4px 0 15px rgba(233, 69, 96, 0.2);
}

.sidebar-header {
  text-align: center;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 20px;
}

.logo-img {
  width: 64px;
  height: 64px;
  object-fit: contain;
  margin-bottom: 8px;
  filter: drop-shadow(0 0 10px rgba(233, 69, 96, 0.5));
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

.sidebar-header h2 {
  color: var(--accent-secondary);
  font-size: 24px;
  margin-bottom: 4px;
}

.sidebar-header p {
  color: var(--text-secondary);
  font-size: 14px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: rgba(233, 69, 96, 0.1);
  border-radius: 12px;
  margin-bottom: 20px;
}

.user-avatar-img {
  width: 44px;
  height: 44px;
  object-fit: contain;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 50%;
  padding: 4px;
}

.user-details {
  display: flex;
  flex-direction: column;
}

.username {
  color: var(--text-primary);
  font-weight: 600;
  font-size: 16px;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.nav-menu::-webkit-scrollbar {
  width: 4px;
}

.nav-menu::-webkit-scrollbar-thumb {
  background: rgba(233, 69, 96, 0.3);
  border-radius: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid transparent;
  border-radius: 12px;
  color: var(--text-primary);
  text-decoration: none;
  transition: all 0.3s ease;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--accent-primary);
  transform: translateX(4px);
}

.nav-item.router-link-exact-active {
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.3) 0%, rgba(255, 107, 157, 0.2) 100%);
  border-color: var(--accent-primary);
  color: var(--accent-secondary);
}

.nav-emoji {
  width: 28px;
  height: 28px;
  object-fit: contain;
  filter: drop-shadow(0 0 4px rgba(233, 69, 96, 0.3));
  transition: transform 0.2s ease;
}

.nav-item:hover .nav-emoji {
  transform: scale(1.15);
}

.nav-label {
  font-size: 15px;
  font-weight: 500;
}

.sidebar-footer {
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
  margin-top: 16px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.logout-btn {
  width: 100%;
}

.system-status {
  margin-top: auto;
  padding: 12px;
  background: rgba(233, 69, 96, 0.1);
  border: 1px solid rgba(233, 69, 96, 0.3);
  border-radius: 10px;
  flex-shrink: 0;
}

.status-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
}

.status-label {
  color: var(--text-secondary);
}

.status-value {
  color: var(--text-secondary);
}

.status-value.active {
  color: #81c784;
}

.main-content {
  flex: 1;
  height: 100%;
  overflow: hidden;
  background: rgba(15, 15, 26, 0.85);
}
</style>
