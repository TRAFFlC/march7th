<template>
  <div class="settings-page">
    <div class="page-header">
      <h1 class="title"><img src="/emojis/三月七_骄傲.png" class="emoji-icon-lg" /> 系统设置</h1>
      <p>配置系统参数</p>
    </div>

    <div class="settings-content">
      <div class="settings-section">
        <div class="section-title">
          <span><img src="/emojis/三月七_盯.png" class="emoji-icon" /> 安全设置</span>
        </div>
        <div class="setting-item">
          <div class="setting-info">
            <label>启用安全过滤器</label>
            <p class="setting-desc">开启后将对用户输入进行安全检测，过滤敏感内容</p>
          </div>
          <label class="toggle-switch">
            <input
              type="checkbox"
              v-model="settings.securityFilterEnabled"
              @change="saveSettings"
            />
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>

      <div class="settings-section">
        <div class="section-title">
          <span>🌐 网络设置</span>
        </div>
        <div class="setting-item">
          <div class="setting-info">
            <label>启用代理</label>
            <p class="setting-desc">为API请求启用代理服务器</p>
          </div>
          <label class="toggle-switch">
            <input
              type="checkbox"
              v-model="settings.proxyEnabled"
              @change="saveSettings"
            />
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div v-if="settings.proxyEnabled" class="setting-item column">
          <div class="setting-info">
            <label>代理地址</label>
          </div>
          <input
            v-model="settings.proxyUrl"
            class="input-field"
            placeholder="http://127.0.0.1:7890"
            @change="saveSettings"
          />
        </div>
      </div>

      <div class="settings-section">
        <div class="section-title">
          <span><img src="/emojis/三月七_骄傲.png" class="emoji-icon" /> 日志设置</span>
        </div>
        <div class="setting-item">
          <div class="setting-info">
            <label>详细日志模式</label>
            <p class="setting-desc">记录更详细的调试信息（可能影响性能）</p>
          </div>
          <label class="toggle-switch">
            <input
              type="checkbox"
              v-model="settings.verboseLogging"
              @change="saveSettings"
            />
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
    </div>

    <div v-if="settingsMessage" class="settings-message" :class="settingsMessageType">
      {{ settingsMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../utils/api'

const settings = ref({
  securityFilterEnabled: true,
  proxyEnabled: false,
  proxyUrl: '',
  verboseLogging: false
})
const settingsMessage = ref('')
const settingsMessageType = ref('success')

onMounted(() => {
  loadSettings()
})

async function loadSettings() {
  try {
    const response = await api.get('/settings')
    if (response.success && response.settings) {
      settings.value = { ...settings.value, ...response.settings }
    }
  } catch (e) {
    console.error('Failed to load settings:', e)
  }
}

async function saveSettings() {
  try {
    await api.put('/settings', settings.value)
    settingsMessage.value = '✅ 设置已保存'
    settingsMessageType.value = 'success'
    setTimeout(() => {
      settingsMessage.value = ''
    }, 3000)
  } catch (e) {
    settingsMessage.value = '❌ 保存失败: ' + (e.detail || '未知错误')
    settingsMessageType.value = 'error'
  }
}
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
.settings-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow: hidden;
}

.page-header {
  margin-bottom: 20px;
}

.page-header p {
  color: var(--text-secondary);
  margin-top: 8px;
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-section {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--accent-secondary);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
}

.setting-item.column {
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.setting-item:not(:last-child) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.setting-info {
  flex: 1;
}

.setting-info label {
  display: block;
  font-weight: 500;
  margin-bottom: 4px;
}

.setting-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 50px;
  height: 28px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.2);
  transition: 0.3s;
  border-radius: 28px;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 22px;
  width: 22px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.3s;
  border-radius: 50%;
}

.toggle-switch input:checked + .toggle-slider {
  background-color: var(--accent-primary);
}

.toggle-switch input:checked + .toggle-slider:before {
  transform: translateX(22px);
}

.settings-message {
  padding: 12px 16px;
  border-radius: 8px;
  margin-top: 16px;
  text-align: center;
}

.settings-message.success {
  background: rgba(129, 199, 132, 0.2);
  color: #81c784;
}

.settings-message.error {
  background: rgba(255, 107, 107, 0.2);
  color: #ff6b6b;
}
</style>
