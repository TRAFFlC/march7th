<template>
  <div class="characters-page">
    <div class="page-header">
      <h1 class="title"><img src="/emojis/三月七_开心.png" class="emoji-icon-lg" /> 角色管理</h1>
      <p>管理和配置角色卡片</p>
    </div>

    <div class="tab-header">
      <button
        :class="['tab-btn', { active: activeTab === 'list' }]"
        @click="activeTab = 'list'"
      >
        <img src="/emojis/三月七_盯.png" class="emoji-icon" /> 角色列表
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'market' }]"
        @click="activeTab = 'market'"
      >
        <img src="/emojis/三月七_买买买.png" class="emoji-icon" /> 官方模板
      </button>
    </div>

    <div class="characters-container" v-if="activeTab === 'list'">
      <div class="character-list">
        <div class="list-header">
          <h3>角色列表</h3>
          <button class="btn btn-primary" @click="newCharacter">
            ➕ 新建角色
          </button>
        </div>

        <div class="list-items">
          <div
            v-for="char in characters"
            :key="char.id"
            :class="['character-item', { selected: editingCharacter?.id === char.id }]"
            @click="selectCharacter(char)"
          >
            <div class="char-avatar">
              <img v-if="char.avatar_path" :src="`/api/avatar/${char.id}`" class="avatar-img" />
              <span v-else>🎭</span>
            </div>
            <div class="char-info">
              <span class="char-name">{{ char.name }}</span>
              <span class="char-model">{{ char.llm_model }}</span>
            </div>
            <span :class="['rag-badge', char.rag_enabled ? 'enabled' : 'disabled']">
              {{ char.rag_enabled ? 'RAG' : '无RAG' }}
            </span>
          </div>
        </div>
      </div>

      <div class="character-editor">
        <div v-if="!editingCharacter" class="empty-editor">
          <span class="empty-icon"><img src="/emojis/三月七_无语.png" class="emoji-icon-lg" /></span>
          <p>选择一个角色进行编辑，或创建新角色</p>
        </div>

        <div v-else class="editor-form">
          <h3>{{ isNewCharacter ? '新建角色' : '编辑角色' }}</h3>

          <div class="form-section">
            <h4>基本信息</h4>
            <div class="form-row">
              <div class="form-group">
                <label>角色ID</label>
                <input
                  v-model="editingCharacter.id"
                  type="text"
                  class="input-field"
                  placeholder="唯一标识符"
                  :disabled="!isNewCharacter"
                />
              </div>
              <div class="form-group">
                <label>角色名称</label>
                <input
                  v-model="editingCharacter.name"
                  type="text"
                  class="input-field"
                  placeholder="显示名称"
                />
              </div>
            </div>
            <div class="form-group">
              <label>头像路径</label>
              <input
                v-model="editingCharacter.avatar_path"
                type="text"
                class="input-field"
                placeholder="头像图片路径（可选）"
              />
            </div>
            <div class="form-group">
              <label>唤醒词 <span class="hint">(桌宠语音唤醒词，默认为角色名称)</span></label>
              <input
                v-model="editingCharacter.wake_word"
                type="text"
                class="input-field"
                placeholder="三月七"
              />
            </div>
          </div>

          <div class="form-section">
            <h4>LLM 配置</h4>
            <div class="form-group" v-if="editingCharacter.api_provider_type === 'ollama'">
              <label>本地模型</label>
              <select v-model="editingCharacter.llm_model" class="input-field">
                <option value="deepseek-r1:8b">deepseek-r1:8b</option>
                <option value="qwen3.5:9b">qwen3.5:9b</option>
              </select>
            </div>
            <div class="form-group" v-else>
              <label>云端模型 <span class="hint">(由 API 配置提供)</span></label>
              <div class="model-display">
                {{ editingCharacter.api_model_name || '请在下方 API 配置中填写模型名称' }}
              </div>
            </div>
            <div class="form-group">
              <label>System Prompt</label>
              <textarea
                v-model="editingCharacter.system_prompt"
                class="input-field"
                placeholder="系统提示词..."
                rows="6"
              ></textarea>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Temperature</label>
                <div class="slider-with-value">
                  <input
                    type="range"
                    v-model="editingCharacter.temperature"
                    min="0.1"
                    max="2"
                    step="0.1"
                    class="slider-input"
                  />
                  <span class="slider-value">{{ editingCharacter.temperature }}</span>
                </div>
              </div>
              <div class="form-group">
                <label>Top P</label>
                <div class="slider-with-value">
                  <input
                    type="range"
                    v-model="editingCharacter.top_p"
                    min="0.1"
                    max="1"
                    step="0.1"
                    class="slider-input"
                  />
                  <span class="slider-value">{{ editingCharacter.top_p }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>🔑 API 配置 <span class="hint">(使用云端模型)</span></h4>
            <div class="form-group">
              <label>Provider 类型</label>
              <select v-model="editingCharacter.api_provider_type" class="input-field" @change="onProviderChange">
                <option value="ollama">Ollama (本地)</option>
                <option value="openai_compatible">OpenAI 兼容 API</option>
              </select>
            </div>
            <template v-if="editingCharacter.api_provider_type === 'openai_compatible'">
              <div class="form-group">
                <label>Base URL</label>
                <input
                  v-model="editingCharacter.api_base_url"
                  type="text"
                  class="input-field"
                  placeholder="https://openrouter.ai/api/v1"
                />
              </div>
              <div class="form-group">
                <label>API Key</label>
                <input
                  v-model="editingCharacter.api_key"
                  type="password"
                  class="input-field"
                  :placeholder="editingCharacter.has_api_key ? '输入新的 API Key 以替换' : 'sk-...'"
                />
              </div>
              <div class="form-group">
                <label>模型名称</label>
                <input
                  v-model="editingCharacter.api_model_name"
                  type="text"
                  class="input-field"
                  placeholder="google/gemma-3-1b-it:free"
                />
              </div>
              <div class="form-group">
                <button class="btn btn-secondary" @click="testApiConnection" :disabled="testingApi">
                  {{ testingApi ? '测试中...' : '🔍 测试连接' }}
                </button>
                <span v-if="apiTestResult" :class="['test-result', apiTestResult.success ? 'success' : 'error']">
                  {{ apiTestResult.message }}
                </span>
              </div>
            </template>
          </div>

          <div class="form-section">
            <h4>RAG 配置</h4>
            <div class="form-group">
              <label>
                <input type="checkbox" v-model="editingCharacter.rag_enabled" />
                启用 RAG
              </label>
            </div>
            <div class="form-group">
              <label>RAG 集合名称</label>
              <input
                v-model="editingCharacter.rag_collection"
                type="text"
                class="input-field"
                placeholder="知识库集合名称"
              />
            </div>
          </div>

          <div class="form-section collapsible">
            <div class="section-header" @click="toggleSection('iterationApi')">
              <h4>🔄 RAG迭代API配置</h4>
              <span class="toggle-icon">{{ expandedSections.iterationApi ? '▼' : '▶' }}</span>
            </div>
            <div v-if="expandedSections.iterationApi" class="section-content">
              <div class="form-group">
                <label>
                  <input type="checkbox" v-model="editingCharacter.use_main_api_for_iteration" @change="onIterationApiToggle" />
                  使用主API配置
                </label>
              </div>
              <template v-if="!editingCharacter.use_main_api_for_iteration">
                <div class="form-group">
                  <label>Provider 类型</label>
                  <select v-model="editingCharacter.iteration_provider_type" class="input-field">
                    <option value="ollama">Ollama (本地)</option>
                    <option value="openai_compatible">OpenAI 兼容 API</option>
                  </select>
                </div>
                <template v-if="editingCharacter.iteration_provider_type === 'openai_compatible'">
                  <div class="form-group">
                    <label>Base URL</label>
                    <input
                      v-model="editingCharacter.iteration_base_url"
                      type="text"
                      class="input-field"
                      placeholder="https://openrouter.ai/api/v1"
                    />
                  </div>
                  <div class="form-group">
                    <label>API Key</label>
                    <input
                      v-model="editingCharacter.iteration_api_key"
                      type="password"
                      class="input-field"
                      :placeholder="editingCharacter.has_iteration_api_key ? '输入新的 API Key 以替换' : 'sk-...'"
                    />
                  </div>
                  <div class="form-group">
                    <label>模型名称</label>
                    <input
                      v-model="editingCharacter.iteration_model_name"
                      type="text"
                      class="input-field"
                      placeholder="google/gemma-3-1b-it:free"
                    />
                  </div>
                </template>
              </template>
            </div>
          </div>

          <div class="form-section collapsible">
            <div class="section-header" @click="toggleSection('emotionApi')">
              <h4>😊 情绪分类API配置</h4>
              <span class="toggle-icon">{{ expandedSections.emotionApi ? '▼' : '▶' }}</span>
            </div>
            <div v-if="expandedSections.emotionApi" class="section-content">
              <div class="form-group">
                <label>
                  <input type="checkbox" v-model="editingCharacter.use_main_api_for_emotion" @change="onEmotionApiToggle" />
                  使用主API配置
                </label>
              </div>
              <template v-if="!editingCharacter.use_main_api_for_emotion">
                <div class="form-group">
                  <label>Provider 类型</label>
                  <select v-model="editingCharacter.emotion_provider_type" class="input-field">
                    <option value="ollama">Ollama (本地)</option>
                    <option value="openai_compatible">OpenAI 兼容 API</option>
                  </select>
                </div>
                <template v-if="editingCharacter.emotion_provider_type === 'openai_compatible'">
                  <div class="form-group">
                    <label>Base URL</label>
                    <input
                      v-model="editingCharacter.emotion_base_url"
                      type="text"
                      class="input-field"
                      placeholder="https://openrouter.ai/api/v1"
                    />
                  </div>
                  <div class="form-group">
                    <label>API Key</label>
                    <input
                      v-model="editingCharacter.emotion_api_key"
                      type="password"
                      class="input-field"
                      :placeholder="editingCharacter.has_emotion_api_key ? '输入新的 API Key 以替换' : 'sk-...'"
                    />
                  </div>
                  <div class="form-group">
                    <label>模型名称</label>
                    <input
                      v-model="editingCharacter.emotion_model_name"
                      type="text"
                      class="input-field"
                      placeholder="google/gemma-3-1b-it:free"
                    />
                  </div>
                </template>
              </template>
            </div>
          </div>

          <div class="form-section">
            <h4>🕐 动态问候语</h4>
            <p class="section-hint">根据时间段自动注入角色开场白</p>
            <div class="form-group">
              <label><img src="/emojis/三月七_开心.png" class="emoji-icon" /> 早晨 (6:00-12:00)</label>
              <input
                v-model="editingCharacter.greeting_morning"
                type="text"
                class="input-field"
                placeholder="早上好呀！今天天气真不错呢～"
              />
            </div>
            <div class="form-group">
              <label>☀️ 下午 (12:00-18:00)</label>
              <input
                v-model="editingCharacter.greeting_afternoon"
                type="text"
                class="input-field"
                placeholder="下午好！有没有好好吃午饭呀？"
              />
            </div>
            <div class="form-group">
              <label><img src="/emojis/三月七_困.png" class="emoji-icon" /> 晚上 (18:00-22:00)</label>
              <input
                v-model="editingCharacter.greeting_evening"
                type="text"
                class="input-field"
                placeholder="晚上好～今天辛苦啦！"
              />
            </div>
            <div class="form-group">
              <label>🌌 深夜 (22:00-6:00)</label>
              <input
                v-model="editingCharacter.greeting_night"
                type="text"
                class="input-field"
                placeholder="这么晚了还没睡呀？要注意休息哦～"
              />
            </div>
          </div>

          <div class="form-actions">
            <button class="btn btn-primary" @click="saveCharacter">
              💾 保存
            </button>
            <button v-if="!isNewCharacter" class="btn btn-danger" @click="deleteCharacter">
              🗑️ 删除
            </button>
            <button class="btn btn-secondary" @click="cancelEdit">
              ❌ 取消
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="market-container" v-if="activeTab === 'market'">
      <div class="market-header">
        <h3><img src="/emojis/三月七_开心.png" class="emoji-icon" /> 官方角色模板</h3>
        <p>由管理员提供的角色模板，点击添加到您的角色列表</p>
      </div>

      <div class="template-grid" v-if="templates.length > 0">
        <div
          v-for="template in templates"
          :key="template.id"
          class="template-card"
        >
          <div class="template-avatar">
              <img v-if="template.avatar_path" :src="`/api/template/avatar/${template.id}`" class="avatar-img" />
              <span v-else>🎭</span>
            </div>
          <div class="template-info">
            <h4>{{ template.name }}</h4>
            <span class="template-id">ID: {{ template.id }}</span>
            <span class="template-model">{{ template.llm_model }}</span>
            <p class="template-preview">{{ template.system_prompt_preview }}</p>
          </div>
          <div class="template-actions">
            <button
              v-if="!isTemplateAdded(template)"
              class="btn btn-primary add-btn"
              @click="importTemplate(template)"
              :disabled="isImporting === template.id"
            >
              {{ isImporting === template.id ? '导入中...' : '➕ 添加' }}
            </button>
            <span v-else class="already-added">✅ 已添加</span>
          </div>
        </div>
      </div>

      <div class="empty-market" v-else>
        <span class="empty-icon">📦</span>
        <p>暂无可用模板</p>
      </div>
    </div>

    <div v-if="message.text" :class="['message', message.type]">
      {{ message.text }}
    </div>

    <div v-if="showConfirmDialog" class="dialog-overlay" @click.self="showConfirmDialog = false">
      <div class="dialog">
        <h4>确认添加角色</h4>
        <p>确定要添加角色「{{ pendingTemplate?.name }}」吗？</p>
        <div class="dialog-actions">
          <button class="btn btn-primary" @click="confirmImport">确认添加</button>
          <button class="btn btn-secondary" @click="showConfirmDialog = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../utils/api'

const characters = ref([])
const templates = ref([])
const editingCharacter = ref(null)
const isNewCharacter = ref(false)
const activeTab = ref('list')
const isImporting = ref(null)
const message = ref({ text: '', type: 'info' })
const showConfirmDialog = ref(false)
const pendingTemplate = ref(null)
const testingApi = ref(false)
const apiTestResult = ref(null)
const expandedSections = ref({
  iterationApi: false,
  emotionApi: false
})

onMounted(async () => {
  await loadCharacters()
  await loadTemplates()
})

function toggleSection(section) {
  expandedSections.value[section] = !expandedSections.value[section]
}

async function loadCharacters() {
  try {
    const response = await api.get('/characters')
    if (response.success) {
      characters.value = response.characters
    }
  } catch (e) {
    console.error('Failed to load characters:', e)
  }
}

async function loadTemplates() {
  try {
    const response = await api.get('/characters/templates')
    if (response.success) {
      templates.value = response.templates
    }
  } catch (e) {
    console.error('Failed to load templates:', e)
  }
}

function selectCharacter(char) {
  isNewCharacter.value = false
  const iterationConfig = char.iteration_api_config
  const emotionConfig = char.emotion_api_config
  editingCharacter.value = {
    ...char,
    wake_word: char.wake_word || '',
    api_provider_type: char.api_config?.provider_type || 'ollama',
    api_base_url: char.api_config?.base_url || '',
    api_key: char.api_config?.api_key || '',
    has_api_key: char.api_config?.has_api_key || false,
    api_model_name: char.api_config?.model_name || '',
    use_main_api_for_iteration: !iterationConfig,
    iteration_provider_type: iterationConfig?.provider_type || 'ollama',
    iteration_base_url: iterationConfig?.base_url || '',
    iteration_api_key: iterationConfig?.api_key || '',
    has_iteration_api_key: iterationConfig?.has_api_key || false,
    iteration_model_name: iterationConfig?.model_name || '',
    use_main_api_for_emotion: !emotionConfig,
    emotion_provider_type: emotionConfig?.provider_type || 'ollama',
    emotion_base_url: emotionConfig?.base_url || '',
    emotion_api_key: emotionConfig?.api_key || '',
    has_emotion_api_key: emotionConfig?.has_api_key || false,
    emotion_model_name: emotionConfig?.model_name || '',
    greeting_morning: char.greeting_templates?.morning || '',
    greeting_afternoon: char.greeting_templates?.afternoon || '',
    greeting_evening: char.greeting_templates?.evening || '',
    greeting_night: char.greeting_templates?.night || '',
    system_prompt: char.llm_config?.system_prompt || '',
    rag_collection: char.rag_config?.collection_name || '',
    rag_enabled: char.rag_config?.enabled ?? true
  }
  apiTestResult.value = null
}

function newCharacter() {
  isNewCharacter.value = true
  editingCharacter.value = {
    id: '',
    name: '',
    avatar_path: '',
    wake_word: '',
    llm_model: 'deepseek-r1:8b',
    system_prompt: '',
    temperature: 1.0,
    top_p: 0.9,
    rag_enabled: true,
    rag_collection: '',
    api_provider_type: 'ollama',
    api_base_url: '',
    api_key: '',
    has_api_key: false,
    api_model_name: '',
    use_main_api_for_iteration: true,
    iteration_provider_type: 'ollama',
    iteration_base_url: '',
    iteration_api_key: '',
    has_iteration_api_key: false,
    iteration_model_name: '',
    use_main_api_for_emotion: true,
    emotion_provider_type: 'ollama',
    emotion_base_url: '',
    emotion_api_key: '',
    has_emotion_api_key: false,
    emotion_model_name: '',
    greeting_morning: '',
    greeting_afternoon: '',
    greeting_evening: '',
    greeting_night: ''
  }
  apiTestResult.value = null
}

function cancelEdit() {
  editingCharacter.value = null
  isNewCharacter.value = false
  apiTestResult.value = null
}

function onProviderChange() {
  const char = editingCharacter.value
  if (char.api_provider_type === 'ollama') {
    char.api_base_url = ''
    char.api_key = ''
    char.api_model_name = ''
  } else if (char.api_provider_type === 'openai_compatible' && !char.api_base_url) {
    char.api_base_url = 'https://openrouter.ai/api/v1'
  }
  apiTestResult.value = null
}

function onIterationApiToggle() {
  const char = editingCharacter.value
  if (!char.use_main_api_for_iteration && char.iteration_provider_type === 'openai_compatible' && !char.iteration_base_url) {
    char.iteration_base_url = 'https://openrouter.ai/api/v1'
  }
}

function onEmotionApiToggle() {
  const char = editingCharacter.value
  if (!char.use_main_api_for_emotion && char.emotion_provider_type === 'openai_compatible' && !char.emotion_base_url) {
    char.emotion_base_url = 'https://openrouter.ai/api/v1'
  }
}

async function testApiConnection() {
  const char = editingCharacter.value
  if (!char.api_base_url || !char.api_key || !char.api_model_name) {
    apiTestResult.value = { success: false, message: '请填写完整的 API 配置' }
    return
  }
  
  testingApi.value = true
  apiTestResult.value = null
  
  try {
    const response = await api.post('/llm/test', {
      provider_type: char.api_provider_type,
      base_url: char.api_base_url,
      api_key: char.api_key,
      model_name: char.api_model_name
    })
    
    if (response.success && response.test_result?.success) {
      apiTestResult.value = {
        success: true,
        message: `连接成功! 延迟: ${response.test_result.latency_ms}ms，正在自动保存...`
      }
      try {
        const savePayload = {
          ...editingCharacter.value,
          api_config: {
            provider_type: editingCharacter.value.api_provider_type || 'ollama',
            base_url: editingCharacter.value.api_base_url || '',
            api_key: editingCharacter.value.api_key || '',
            model_name: editingCharacter.value.api_model_name || ''
          }
        }
        delete savePayload.api_provider_type
        delete savePayload.api_base_url
        delete savePayload.api_key
        delete savePayload.api_model_name
        await api.post('/characters', savePayload)
        apiTestResult.value = {
          success: true,
          message: `连接成功! 延迟: ${response.test_result.latency_ms}ms，配置已自动保存`
        }
      } catch (saveErr) {
        apiTestResult.value = {
          success: true,
          message: `连接成功! 但自动保存失败: ${saveErr.detail || '未知错误'}`
        }
      }
    } else {
      apiTestResult.value = {
        success: false,
        message: response.test_result?.message || '连接失败'
      }
    }
  } catch (e) {
    apiTestResult.value = {
      success: false,
      message: e.detail || e.message || '测试失败'
    }
  } finally {
    testingApi.value = false
  }
}

async function saveCharacter() {
  if (!editingCharacter.value.id || !editingCharacter.value.name) {
    showMessage('请填写角色ID和名称', 'error')
    return
  }

  try {
    const isMaskedKey = (key) => key && key.startsWith('*')
    
    const iterationApiConfig = editingCharacter.value.use_main_api_for_iteration ? null : {
      provider_type: editingCharacter.value.iteration_provider_type || 'ollama',
      base_url: editingCharacter.value.iteration_base_url || '',
      api_key: isMaskedKey(editingCharacter.value.iteration_api_key) ? '' : (editingCharacter.value.iteration_api_key || ''),
      model_name: editingCharacter.value.iteration_model_name || ''
    }
    const emotionApiConfig = editingCharacter.value.use_main_api_for_emotion ? null : {
      provider_type: editingCharacter.value.emotion_provider_type || 'ollama',
      base_url: editingCharacter.value.emotion_base_url || '',
      api_key: isMaskedKey(editingCharacter.value.emotion_api_key) ? '' : (editingCharacter.value.emotion_api_key || ''),
      model_name: editingCharacter.value.emotion_model_name || ''
    }

    const payload = {
      ...editingCharacter.value,
      api_config: {
        provider_type: editingCharacter.value.api_provider_type || 'ollama',
        base_url: editingCharacter.value.api_base_url || '',
        api_key: isMaskedKey(editingCharacter.value.api_key) ? '' : (editingCharacter.value.api_key || ''),
        model_name: editingCharacter.value.api_model_name || ''
      },
      iteration_api_config: iterationApiConfig,
      emotion_api_config: emotionApiConfig,
      greeting_templates: {
        morning: editingCharacter.value.greeting_morning || '',
        afternoon: editingCharacter.value.greeting_afternoon || '',
        evening: editingCharacter.value.greeting_evening || '',
        night: editingCharacter.value.greeting_night || ''
      }
    }
    delete payload.api_provider_type
    delete payload.api_base_url
    delete payload.api_key
    delete payload.api_model_name
    delete payload.greeting_morning
    delete payload.greeting_afternoon
    delete payload.greeting_evening
    delete payload.greeting_night
    delete payload.use_main_api_for_iteration
    delete payload.iteration_provider_type
    delete payload.iteration_base_url
    delete payload.iteration_api_key
    delete payload.iteration_model_name
    delete payload.use_main_api_for_emotion
    delete payload.emotion_provider_type
    delete payload.emotion_base_url
    delete payload.emotion_api_key
    delete payload.emotion_model_name

    const response = await api.post('/characters', payload)
    if (response.success) {
      await loadCharacters()
      editingCharacter.value = null
      isNewCharacter.value = false
      showMessage('角色保存成功', 'success')
    }
  } catch (e) {
    showMessage('保存失败: ' + (e.detail || '未知错误'), 'error')
  }
}

async function deleteCharacter() {
  if (!confirm(`确定要删除角色 "${editingCharacter.value.name}" 吗？`)) return

  try {
    await api.delete(`/characters/${editingCharacter.value.id}`)
    await loadCharacters()
    editingCharacter.value = null
    isNewCharacter.value = false
    showMessage('角色已删除', 'success')
  } catch (e) {
    showMessage('删除失败: ' + (e.detail || '未知错误'), 'error')
  }
}

function importTemplate(template) {
  pendingTemplate.value = template
  showConfirmDialog.value = true
}

function isTemplateAdded(template) {
  return characters.value.some(char => char.id === template.id)
}

async function confirmImport() {
  if (!pendingTemplate.value) return

  isImporting.value = pendingTemplate.value.id
  showConfirmDialog.value = false

  try {
    const response = await api.post(`/characters/import/${pendingTemplate.value.id}`)
    if (response.success) {
      showMessage(`角色「${pendingTemplate.value.name}」添加成功！`, 'success')
      await loadCharacters()
    }
  } catch (e) {
    showMessage('添加失败: ' + (e.detail || '未知错误'), 'error')
  } finally {
    isImporting.value = null
    pendingTemplate.value = null
  }
}

function showMessage(text, type = 'info') {
  message.value = { text, type }
  setTimeout(() => {
    message.value = { text: '', type: 'info' }
  }, 3000)
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
.characters-page {
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

.tab-header {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.tab-btn {
  padding: 12px 24px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 14px;
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: var(--accent-primary);
}

.tab-btn.active {
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.3) 0%, rgba(255, 107, 157, 0.2) 100%);
  border-color: var(--accent-primary);
  color: var(--text-primary);
}

.characters-container {
  flex: 1;
  display: flex;
  gap: 20px;
  overflow: hidden;
}

.character-list {
  width: 320px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.list-header h3 {
  color: var(--accent-secondary);
}

.list-items {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.character-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.character-item:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--accent-primary);
}

.character-item.selected {
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.3) 0%, rgba(255, 107, 157, 0.2) 100%);
  border-color: var(--accent-primary);
}

.char-avatar {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  overflow: hidden;
}

.char-avatar .avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.char-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.char-name {
  font-weight: 500;
}

.char-model {
  font-size: 12px;
  color: var(--text-secondary);
}

.rag-badge {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
}

.rag-badge.enabled {
  background: rgba(129, 199, 132, 0.2);
  color: #81c784;
}

.rag-badge.disabled {
  background: rgba(255, 152, 0, 0.2);
  color: #ff9800;
}

.hint {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: normal;
}

.model-display {
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--accent-secondary);
  font-size: 14px;
}

.test-result {
  margin-left: 12px;
  font-size: 13px;
}

.test-result.success {
  color: #81c784;
}

.test-result.error {
  color: #f44336;
}

.character-editor {
  flex: 1;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 24px;
  overflow-y: auto;
}

.empty-editor {
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

.editor-form h3 {
  color: var(--accent-secondary);
  margin-bottom: 24px;
}

.form-section {
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
}

.form-section:last-of-type {
  border-bottom: none;
}

.form-section.collapsible {
  padding-bottom: 0;
}

.form-section.collapsible .section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  transition: background 0.3s ease;
}

.form-section.collapsible .section-header:hover {
  background: rgba(255, 255, 255, 0.1);
}

.form-section.collapsible .section-header h4 {
  margin: 0;
}

.form-section.collapsible .toggle-icon {
  color: var(--text-secondary);
  font-size: 12px;
}

.form-section.collapsible .section-content {
  padding: 16px 0 24px 0;
}

.form-section h4 {
  color: var(--text-primary);
  margin-bottom: 16px;
  font-size: 16px;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-row .form-group {
  flex: 1;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 8px;
}

.form-group textarea {
  resize: none;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.section-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 12px 0;
}

.market-container {
  flex: 1;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 24px;
  overflow-y: auto;
}

.market-header {
  margin-bottom: 24px;
}

.market-header h3 {
  color: var(--accent-secondary);
  margin-bottom: 8px;
}

.market-header p {
  color: var(--text-secondary);
  font-size: 14px;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.template-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: all 0.3s ease;
}

.template-card:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: var(--accent-primary);
}

.template-avatar {
  width: 60px;
  height: 60px;
  background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  overflow: hidden;
  flex-shrink: 0;
}

.template-avatar .avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.template-info {
  flex: 1;
}

.template-info h4 {
  color: var(--text-primary);
  margin-bottom: 8px;
  font-size: 18px;
}

.template-id {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.template-model {
  display: block;
  font-size: 12px;
  color: var(--accent-secondary);
  margin-bottom: 12px;
}

.template-preview {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.template-actions {
  display: flex;
  justify-content: flex-end;
}

.empty-market {
  height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.message {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 16px 24px;
  border-radius: 12px;
  font-size: 14px;
  animation: slideIn 0.3s ease;
  z-index: 1000;
}

.message.success {
  background: rgba(129, 199, 132, 0.9);
  color: #fff;
}

.message.error {
  background: rgba(244, 67, 54, 0.9);
  color: #fff;
}

.message.info {
  background: rgba(33, 150, 243, 0.9);
  color: #fff;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.dialog-overlay {
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

.dialog {
  background: rgba(30, 30, 30, 0.95);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
}

.dialog h4 {
  color: var(--text-primary);
  margin-bottom: 16px;
}

.dialog p {
  color: var(--text-secondary);
  margin-bottom: 24px;
}

.dialog-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.slider-with-value {
  display: flex;
  align-items: center;
  gap: 10px;
}

.slider-input {
  flex: 1;
}

.slider-value {
  min-width: 36px;
  text-align: right;
  font-size: 13px;
  color: var(--accent-primary);
  font-weight: bold;
}

.already-added {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: rgba(129, 199, 132, 0.2);
  color: #81c784;
  border-radius: 6px;
  font-size: 13px;
  cursor: default;
}

</style>