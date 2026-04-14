<template>
  <div class="llm-page">
    <div class="page-header">
      <h1 class="title"><img src="/emojis/三月七_biu.png" class="emoji-icon-lg" /> LLM 独立测试</h1>
      <p>单独测试大语言模型功能，不生成语音</p>
    </div>

    <div class="llm-container">
      <div class="llm-main">
        <div class="messages-area" ref="messagesRef">
          <div v-if="messages.length === 0" class="empty-state">
            <img src="/emojis/三月七_biu.png" class="emoji-icon-xl" />
            <p>输入问题开始测试</p>
          </div>
          
          <div v-for="(msg, index) in messages" :key="index" class="message-item">
            <div :class="['message', msg.role]">
              <div class="message-label">
                <template v-if="msg.role === 'user'">用户</template>
                <template v-else><img src="/emojis/三月七_biu.png" class="emoji-icon" /> 助手</template>
              </div>
              <div class="message-content">{{ msg.content }}</div>
            </div>
          </div>

          <div v-if="loading" class="loading-indicator">
            <span class="loading-spinner"></span>
            <span>生成中...</span>
          </div>
        </div>

        <div class="input-area">
          <textarea 
            v-model="userInput"
            class="input-field"
            placeholder="输入问题..."
            rows="4"
            @keydown.enter.exact.prevent="sendMessage"
            :disabled="loading"
          ></textarea>
          
          <div class="input-actions">
            <button class="btn btn-secondary" @click="clearHistory" :disabled="loading">
              🗑️ 清除
            </button>
            <button 
              class="btn btn-primary" 
              @click="sendMessage"
              :disabled="loading || !userInput.trim()"
            >
              🚀 发送
            </button>
          </div>
        </div>
      </div>

      <div class="llm-settings">
        <h3><img src="/emojis/三月七_买买买.png" class="emoji-icon" /> 参数设置</h3>
        
        <div class="setting-group">
          <label>测试模式</label>
          <select v-model="testMode" class="input-field" @change="onModeChange">
            <option value="character">角色模式</option>
            <option value="api">API 模式</option>
          </select>
        </div>

        <template v-if="testMode === 'character'">
          <div class="setting-group">
            <label>角色选择</label>
            <select v-model="selectedCharacter" class="input-field">
              <option v-for="char in characters" :key="char.id" :value="char.id">
                {{ char.name }}
              </option>
            </select>
          </div>

          <div class="setting-group">
            <label>本地模型</label>
            <select v-model="selectedModel" class="input-field">
              <option value="deepseek-r1:8b">deepseek-r1:8b</option>
              <option value="qwen3.5:9b">qwen3.5:9b</option>
            </select>
          </div>
        </template>

        <template v-else>
          <div class="setting-group">
            <label>Provider 类型</label>
            <select v-model="apiProviderType" class="input-field" @change="onProviderTypeChange">
              <option value="ollama">Ollama (本地)</option>
              <option value="openai_compatible">OpenAI 兼容 API</option>
            </select>
          </div>

          <template v-if="apiProviderType === 'openai_compatible'">
            <div class="setting-group">
              <label>API 提供商 (快速选择)</label>
              <select v-model="selectedPreset" class="input-field" @change="onPresetChange">
                <option value="">自定义</option>
                <option value="openrouter">OpenRouter</option>
                <option value="openai">OpenAI</option>
                <option value="deepseek">DeepSeek</option>
                <option value="moonshot">Moonshot (月之暗面)</option>
                <option value="zhipu">智谱 AI</option>
              </select>
            </div>
            <div class="setting-group">
              <label>
                Base URL
                <span class="hint" v-if="selectedPreset === 'openrouter'">OpenRouter 会自动路由到指定模型</span>
              </label>
              <input v-model="apiBaseUrl" type="text" class="input-field" placeholder="https://openrouter.ai/api/v1" />
            </div>
            <div class="setting-group">
              <label>API Key</label>
              <input v-model="apiKey" type="password" class="input-field" placeholder="sk-..." />
            </div>
            <div class="setting-group">
              <label>模型名称</label>
              <input v-model="apiModelName" type="text" class="input-field" placeholder="google/gemma-3-1b-it:free" />
              <div class="model-hint" v-if="selectedPreset === 'openrouter'">
                <a href="https://openrouter.ai/models?q=:free" target="_blank">查看免费模型列表</a>
              </div>
            </div>
          </template>

          <div class="setting-group" v-if="apiProviderType === 'ollama'">
            <label>本地模型</label>
            <select v-model="selectedModel" class="input-field">
              <option value="deepseek-r1:8b">deepseek-r1:8b</option>
              <option value="qwen3.5:9b">qwen3.5:9b</option>
            </select>
          </div>

          <div class="setting-group">
            <label>System Prompt <span class="hint">(可选)</span></label>
            <textarea 
              v-model="apiSystemPrompt" 
              class="input-field system-prompt-input"
              placeholder="你是一个有帮助的AI助手..."
              rows="3"
            ></textarea>
          </div>

          <div class="setting-group">
            <button class="btn btn-secondary btn-sm" @click="testConnection" :disabled="testingConnection">
              {{ testingConnection ? '测试中...' : '🔍 测试连接' }}
            </button>
            <span v-if="connectionResult" :class="['connection-result', connectionResult.success ? 'success' : 'error']">
              {{ connectionResult.message }}
            </span>
          </div>
        </template>

        <div class="setting-group">
          <label>Temperature: {{ temperature }}</label>
          <input type="range" v-model="temperature" min="0.1" max="2" step="0.1" />
        </div>

        <div class="setting-group">
          <label>Top P: {{ topP }}</label>
          <input type="range" v-model="topP" min="0.1" max="1" step="0.1" />
        </div>

        <div class="setting-group" v-if="testMode === 'character'">
          <label>
            <input type="checkbox" v-model="useRag" />
            启用 RAG
          </label>
        </div>

        <div class="debug-info" v-if="lastDebug">
          <h4><img src="/emojis/三月七_骄傲.png" class="emoji-icon" /> 调试信息</h4>
          <div class="debug-item">
            <span>响应时间:</span>
            <span>{{ lastDebug.responseTime }}s</span>
          </div>
          <div class="debug-item">
            <span>输入Token:</span>
            <span>{{ lastDebug.inputTokens }}</span>
          </div>
          <div class="debug-item">
            <span>输出Token:</span>
            <span>{{ lastDebug.outputTokens }}</span>
          </div>
          <div class="debug-item">
            <span>历史轮数:</span>
            <span>{{ lastDebug.historyTurns }}</span>
          </div>
        </div>

        <div class="compare-section">
          <h4><img src="/emojis/三月七_盯.png" class="emoji-icon" /> 对比测试</h4>
          <p class="compare-hint">同一输入，不同模型/参数对比</p>
          <div class="setting-group">
            <label>对比模型</label>
            <select v-model="compareModel" class="input-field">
              <option value="deepseek-r1:8b">deepseek-r1:8b</option>
              <option value="qwen3.5:9b">qwen3.5:9b</option>
            </select>
          </div>
          <div class="setting-group">
            <label>对比 Temperature: {{ compareTemperature }}</label>
            <input type="range" v-model="compareTemperature" min="0.1" max="2" step="0.1" />
          </div>
          <button 
            class="btn btn-secondary btn-sm compare-btn" 
            @click="runCompareTest" 
            :disabled="loading || compareLoading || !userInput.trim()"
          >
            {{ compareLoading ? '对比中...' : '⚖️ 运行对比' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="compareResults" class="compare-results">
      <div class="compare-header">
        <span><img src="/emojis/三月七_盯.png" class="emoji-icon" /> 对比结果</span>
        <button class="btn-close" @click="compareResults = null">×</button>
      </div>
      <div class="compare-grid">
        <div class="compare-col">
          <div class="compare-col-header">当前配置</div>
          <div class="compare-meta">
            <span>{{ testMode === 'character' ? selectedModel : (apiProviderType === 'ollama' ? selectedModel : apiModelName) }}</span>
            <span>T={{ temperature }} P={{ topP }}</span>
          </div>
          <div class="compare-content">{{ compareResults.current.response }}</div>
          <div class="compare-stats">
            <span><img src="/emojis/三月七_困.png" class="emoji-icon" /> {{ compareResults.current.time }}s</span>
            <span>📥 {{ compareResults.current.inputTokens }}tk</span>
            <span>📤 {{ compareResults.current.outputTokens }}tk</span>
          </div>
        </div>
        <div class="compare-col">
          <div class="compare-col-header">对比配置</div>
          <div class="compare-meta">
            <span>{{ compareModel }}</span>
            <span>T={{ compareTemperature }} P={{ topP }}</span>
          </div>
          <div class="compare-content">{{ compareResults.compare.response }}</div>
          <div class="compare-stats">
            <span><img src="/emojis/三月七_困.png" class="emoji-icon" /> {{ compareResults.compare.time }}s</span>
            <span>📥 {{ compareResults.compare.inputTokens }}tk</span>
            <span>📤 {{ compareResults.compare.outputTokens }}tk</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../utils/api'

const API_PRESETS = {
  openrouter: {
    base_url: 'https://openrouter.ai/api/v1',
    default_model: 'google/gemma-3-1b-it:free'
  },
  openai: {
    base_url: 'https://api.openai.com/v1',
    default_model: 'gpt-3.5-turbo'
  },
  deepseek: {
    base_url: 'https://api.deepseek.com/v1',
    default_model: 'deepseek-chat'
  },
  moonshot: {
    base_url: 'https://api.moonshot.cn/v1',
    default_model: 'moonshot-v1-8k'
  },
  zhipu: {
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    default_model: 'glm-4-flash'
  }
}

const characters = ref([])
const selectedCharacter = ref(null)
const selectedModel = ref('deepseek-r1:8b')
const temperature = ref(1.0)
const topP = ref(0.9)
const useRag = ref(true)

const testMode = ref('character')
const apiProviderType = ref('ollama')
const selectedPreset = ref('')
const apiBaseUrl = ref('')
const apiKey = ref('')
const apiModelName = ref('')
const apiSystemPrompt = ref('')
const testingConnection = ref(false)
const connectionResult = ref(null)

const messages = ref([])
const userInput = ref('')
const loading = ref(false)
const lastDebug = ref(null)
const messagesRef = ref(null)

const compareModel = ref('qwen3.5:9b')
const compareTemperature = ref(1.0)
const compareLoading = ref(false)
const compareResults = ref(null)

onMounted(async () => {
  try {
    const response = await api.get('/characters')
    if (response.success) {
      characters.value = response.characters
      if (characters.value.length > 0) {
        selectedCharacter.value = characters.value[0].id
      }
    }
  } catch (e) {
    console.error('Failed to load characters:', e)
  }
})

function onModeChange() {
  connectionResult.value = null
  if (testMode.value === 'api' && apiProviderType.value === 'openai_compatible' && !apiBaseUrl.value) {
    selectedPreset.value = 'openrouter'
    apiBaseUrl.value = API_PRESETS.openrouter.base_url
    apiModelName.value = API_PRESETS.openrouter.default_model
  }
}

function onProviderTypeChange() {
  selectedPreset.value = ''
  connectionResult.value = null
  if (apiProviderType.value === 'openai_compatible' && !apiBaseUrl.value) {
    selectedPreset.value = 'openrouter'
    apiBaseUrl.value = API_PRESETS.openrouter.base_url
    apiModelName.value = API_PRESETS.openrouter.default_model
  }
}

function onPresetChange() {
  if (selectedPreset.value && API_PRESETS[selectedPreset.value]) {
    const preset = API_PRESETS[selectedPreset.value]
    apiBaseUrl.value = preset.base_url
    if (!apiModelName.value || apiModelName.value === API_PRESETS.openrouter.default_model) {
      apiModelName.value = preset.default_model
    }
  }
  connectionResult.value = null
}

async function testConnection() {
  if (apiProviderType.value === 'openai_compatible') {
    if (!apiBaseUrl.value || !apiKey.value || !apiModelName.value) {
      connectionResult.value = { success: false, message: '请填写完整配置' }
      return
    }
  }

  testingConnection.value = true
  connectionResult.value = null

  try {
    const response = await api.post('/llm/test', {
      provider_type: apiProviderType.value,
      base_url: apiBaseUrl.value,
      api_key: apiKey.value,
      model_name: apiProviderType.value === 'openai_compatible' ? apiModelName.value : selectedModel.value
    })

    if (response.success && response.test_result?.success) {
      connectionResult.value = {
        success: true,
        message: `成功! 延迟: ${response.test_result.latency_ms}ms`
      }
    } else {
      connectionResult.value = {
        success: false,
        message: response.test_result?.message || '连接失败'
      }
    }
  } catch (e) {
    connectionResult.value = {
      success: false,
      message: e.detail || e.message || '测试失败'
    }
  } finally {
    testingConnection.value = false
  }
}

async function sendMessage() {
  if (!userInput.value.trim() || loading.value) return
  
  const message = userInput.value.trim()
  messages.value.push({ role: 'user', content: message })
  userInput.value = ''
  loading.value = true
  
  try {
    let response

    if (testMode.value === 'api') {
      response = await api.post('/llm/chat-direct', {
        message,
        provider_type: apiProviderType.value,
        base_url: apiBaseUrl.value,
        api_key: apiKey.value,
        model_name: apiProviderType.value === 'openai_compatible' ? apiModelName.value : selectedModel.value,
        temperature: temperature.value,
        top_p: topP.value,
        system_prompt: apiSystemPrompt.value
      })
    } else {
      response = await api.post('/llm/chat', {
        message,
        character_id: selectedCharacter.value,
        model: selectedModel.value,
        temperature: temperature.value,
        top_p: topP.value,
        use_rag: useRag.value
      })
    }
    
    if (response.success) {
      messages.value.push({ role: 'assistant', content: response.response })
      lastDebug.value = {
        responseTime: response.debug?.response_time || 0,
        inputTokens: response.debug?.input_tokens || 0,
        outputTokens: response.debug?.output_tokens || 0,
        historyTurns: response.debug?.history_turns || 0
      }
    } else {
      messages.value.push({ role: 'assistant', content: '响应格式错误' })
    }
  } catch (e) {
    messages.value.push({ role: 'assistant', content: `错误: ${e.detail || e.message || '请求失败'}` })
  } finally {
    loading.value = false
  }
}

async function clearHistory() {
  try {
    await api.post('/llm/clear')
    messages.value = []
    lastDebug.value = null
  } catch (e) {
    console.error('Failed to clear:', e)
  }
}

async function runCompareTest() {
  if (!userInput.value.trim() || loading.value || compareLoading.value) return
  
  const message = userInput.value.trim()
  compareLoading.value = true
  compareResults.value = null
  
  try {
    const [currentRes, compareRes] = await Promise.all([
      testMode.value === 'api'
        ? api.post('/llm/chat-direct', {
            message,
            provider_type: apiProviderType.value,
            base_url: apiBaseUrl.value,
            api_key: apiKey.value,
            model_name: apiProviderType.value === 'openai_compatible' ? apiModelName.value : selectedModel.value,
            temperature: temperature.value,
            top_p: topP.value
          })
        : api.post('/llm/chat', {
            message,
            character_id: selectedCharacter.value,
            model: selectedModel.value,
            temperature: temperature.value,
            top_p: topP.value,
            use_rag: useRag.value
          }),
      api.post('/llm/chat', {
        message,
        character_id: selectedCharacter.value,
        model: compareModel.value,
        temperature: compareTemperature.value,
        top_p: topP.value,
        use_rag: useRag.value
      })
    ])
    
    compareResults.value = {
      current: {
        response: currentRes.success ? currentRes.response : `错误: ${currentRes.detail || '请求失败'}`,
        time: currentRes.debug?.response_time || 0,
        inputTokens: currentRes.debug?.input_tokens || 0,
        outputTokens: currentRes.debug?.output_tokens || 0
      },
      compare: {
        response: compareRes.success ? compareRes.response : `错误: ${compareRes.detail || '请求失败'}`,
        time: compareRes.debug?.response_time || 0,
        inputTokens: compareRes.debug?.input_tokens || 0,
        outputTokens: compareRes.debug?.output_tokens || 0
      }
    }
  } catch (e) {
    console.error('Compare test failed:', e)
  } finally {
    compareLoading.value = false
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
.emoji-icon-xl {
  width: 64px;
  height: 64px;
  object-fit: contain;
  vertical-align: middle;
  display: inline-block;
  margin-bottom: 16px;
}
.llm-page {
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

.llm-container {
  flex: 1;
  display: flex;
  gap: 20px;
  overflow: hidden;
}

.llm-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  overflow: hidden;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.message-item {
  margin-bottom: 20px;
}

.message {
  padding: 16px;
  border-radius: 12px;
}

.message.user {
  background: rgba(102, 126, 234, 0.2);
  border-left: 3px solid #667eea;
}

.message.assistant {
  background: rgba(233, 69, 96, 0.1);
  border-left: 3px solid var(--accent-primary);
}

.message-label {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.message-content {
  line-height: 1.7;
  white-space: pre-wrap;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--accent-secondary);
  padding: 16px;
}

.input-area {
  padding: 16px;
  background: rgba(0, 0, 0, 0.3);
  border-top: 1px solid var(--border-color);
}

.input-area textarea {
  resize: none;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
}

.llm-settings {
  width: 280px;
  flex-shrink: 0;
  max-height: calc(100vh - 180px);
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 20px;
  overflow-y: auto;
}

.llm-settings h3 {
  color: var(--accent-secondary);
  margin-bottom: 20px;
}

.setting-group {
  margin-bottom: 16px;
}

.setting-group label {
  display: block;
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 8px;
}

.setting-group input[type="range"] {
  width: 100%;
}

.setting-group input[type="checkbox"] {
  margin-right: 8px;
}

.btn-sm {
  padding: 8px 16px;
  font-size: 13px;
}

.connection-result {
  display: block;
  margin-top: 8px;
  font-size: 13px;
}

.connection-result.success {
  color: #81c784;
}

.connection-result.error {
  color: #f44336;
}

.hint {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: normal;
  margin-left: 8px;
}

.model-hint {
  margin-top: 6px;
  font-size: 12px;
}

.model-hint a {
  color: var(--accent-secondary);
  text-decoration: none;
}

.model-hint a:hover {
  text-decoration: underline;
}

.system-prompt-input {
  resize: none;
  font-size: 13px;
}

.debug-info {
  margin-top: 24px;
  padding: 16px;
  background: rgba(233, 69, 96, 0.1);
  border-radius: 12px;
}

.debug-info h4 {
  color: var(--accent-secondary);
  margin-bottom: 12px;
}

.debug-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 14px;
}

.debug-item span:first-child {
  color: var(--text-secondary);
}

.compare-section {
  margin-top: 24px;
  padding: 16px;
  background: rgba(102, 126, 234, 0.1);
  border-radius: 12px;
}

.compare-section h4 {
  color: #667eea;
  margin-bottom: 4px;
}

.compare-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 12px 0;
}

.compare-btn {
  margin-top: 8px;
  width: 100%;
}

.compare-results {
  margin-top: 20px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  overflow: hidden;
}

.compare-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: rgba(102, 126, 234, 0.15);
  font-weight: 500;
  color: #667eea;
}

.btn-close {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 20px;
  cursor: pointer;
  padding: 4px 8px;
}

.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
}

.compare-col {
  padding: 16px;
  border-right: 1px solid var(--border-color);
}

.compare-col:last-child {
  border-right: none;
}

.compare-col-header {
  font-weight: 600;
  color: var(--accent-secondary);
  margin-bottom: 8px;
  font-size: 14px;
}

.compare-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.compare-content {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  max-height: 200px;
  overflow-y: auto;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  margin-bottom: 10px;
}

.compare-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
