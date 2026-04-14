<template>
  <div class="history-panel" :class="{ open: isOpen }">
    <div class="history-overlay" @click="$emit('close')"></div>
    <div class="history-content">
      <div class="history-header">
        <h3>历史对话</h3>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>
      
      <div v-if="loading" class="history-loading">
        <span class="loading-spinner"></span>
        <span>加载中...</span>
      </div>
      
      <div v-else-if="conversations.length === 0" class="history-empty">
        <span class="empty-icon">📝</span>
        <p>暂无历史对话</p>
      </div>
      
      <div v-else class="history-list">
        <div 
          v-for="conv in conversations" 
          :key="conv.id"
          class="history-item"
          @click="$emit('select', conv)"
        >
          <div class="item-header">
            <span class="item-character">{{ conv.character || '默认角色' }}</span>
            <span class="item-time">{{ formatTime(conv.timestamp) }}</span>
          </div>
          <div class="item-preview">
            <span class="preview-label">用户:</span>
            <span class="preview-text">{{ truncate(conv.user_input, 50) }}</span>
          </div>
          <div class="item-preview">
            <span class="preview-label">回复:</span>
            <span class="preview-text">{{ truncate(conv.bot_reply, 50) }}</span>
          </div>
          <div v-if="conv.rating" class="item-rating">
            <span v-for="i in conv.rating" :key="i">⭐</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../utils/api'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'select'])

const conversations = ref([])
const loading = ref(false)

watch(() => props.isOpen, async (newVal) => {
  if (newVal) {
    await loadHistory()
  }
})

async function loadHistory() {
  loading.value = true
  try {
    const response = await api.get('/chat/history', { limit: 20 })
    if (response.success) {
      conversations.value = response.conversations
    }
  } catch (e) {
    console.error('Failed to load history:', e)
  } finally {
    loading.value = false
  }
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  return timestamp.replace('T', ' ').substring(0, 16)
}

function truncate(text, length) {
  if (!text) return ''
  return text.length > length ? text.substring(0, length) + '...' : text
}
</script>

<style scoped>
.history-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 100%;
  height: 100%;
  z-index: 1000;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.history-panel.open {
  pointer-events: auto;
  opacity: 1;
}

.history-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
}

.history-content {
  position: absolute;
  top: 0;
  right: 0;
  width: 380px;
  height: 100%;
  background: var(--bg-secondary);
  border-left: 2px solid var(--accent-primary);
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.3s ease;
}

.history-panel.open .history-content {
  transform: translateX(0);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.2) 0%, rgba(255, 107, 157, 0.1) 100%);
}

.history-header h3 {
  margin: 0;
  color: var(--accent-secondary);
  font-size: 18px;
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  color: var(--text-primary);
  font-size: 24px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: rgba(233, 69, 96, 0.3);
}

.history-loading,
.history-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  gap: 12px;
}

.empty-icon {
  font-size: 48px;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.history-item {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.history-item:hover {
  background: rgba(233, 69, 96, 0.1);
  border-color: var(--accent-primary);
  transform: translateX(-4px);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.item-character {
  font-size: 13px;
  color: var(--accent-secondary);
  font-weight: 500;
}

.item-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.item-preview {
  font-size: 13px;
  margin-bottom: 6px;
  line-height: 1.4;
}

.preview-label {
  color: var(--text-secondary);
  margin-right: 6px;
}

.preview-text {
  color: var(--text-primary);
}

.item-rating {
  margin-top: 8px;
  font-size: 12px;
}
</style>
