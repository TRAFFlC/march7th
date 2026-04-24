<template>
  <div class="chat-page">
    <div class="session-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <span v-if="!sidebarCollapsed">会话列表</span>
        <button class="btn-collapse" @click="sidebarCollapsed = !sidebarCollapsed">
          {{ sidebarCollapsed ? '▶' : '◀' }}
        </button>
      </div>
      <div v-if="!sidebarCollapsed" class="sidebar-content">
        <button class="btn btn-primary btn-new-session" @click="createNewSession" :disabled="!selectedCharacter">
          ➕ 新建会话
        </button>
        <div class="session-list">
          <div v-if="sessionsLoading" class="session-loading">加载中...</div>
          <div v-else-if="sessions.length === 0" class="session-empty">暂无会话</div>
          <div
            v-for="session in sessions"
            :key="session.id"
            :class="['session-item', { active: currentSessionId === session.id }]"
            @click="switchSession(session)"
            @contextmenu.prevent="showSessionMenu($event, session)"
          >
            <div class="session-char-name">{{ getCharacterName(session.character_id) }}</div>
            <div v-if="editingSessionId === session.id" class="session-title-edit">
              <input v-model="editingTitle" @keyup.enter="saveSessionTitle(session)" @blur="saveSessionTitle(session)" 
                class="title-input" placeholder="输入对话名称" />
            </div>
            <div v-else class="session-summary" @dblclick="startEditTitle(session)">
              {{ getSessionSummary(session) }}
              <span class="edit-title-btn" @click.stop="startEditTitle(session)">✏️</span>
            </div>
            <div class="session-meta">
              <span class="session-count"><img src="/emojis/三月七_悄悄话.png" class="emoji-icon" /> {{ session.message_count || 0 }}</span>
              <span class="session-time">{{ formatSessionTime(session.last_message_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-main">
      <div class="page-header">
        <div class="header-left">
          <h1 class="title">全流程对话</h1>
          <p>与虚拟角色聊天，她会用语音回复你</p>
        </div>
        <div class="header-actions">
          <button class="btn btn-secondary history-btn" @click="showHistory = true">
            历史记录
          </button>
          <button class="btn btn-secondary" @click="showSearch = !showSearch">
            🔍 搜索
          </button>
        </div>
      </div>

    <div v-if="showSearch" class="search-panel">
      <div class="search-input-row">
        <input
          v-model="searchKeyword"
          type="text"
          class="input-field"
          placeholder="搜索历史对话..."
          @keydown.enter="searchHistory"
        />
        <button class="btn btn-primary" @click="searchHistory" :disabled="searching">
          {{ searching ? '搜索中...' : '搜索' }}
        </button>
        <button class="btn btn-secondary" @click="clearSearch">清除</button>
      </div>
      <div v-if="searchResults.length > 0" class="search-results">
        <div
          v-for="(result, index) in searchResults"
          :key="index"
          class="search-result-item"
          @click="restoreSearchResult(result)"
        >
          <div class="result-header">
            <span class="result-time">{{ formatTime(result.timestamp) }}</span>
          </div>
          <div class="result-content">
            <div class="result-user">👤 <span v-html="highlightKeyword(result.user_input)"></span></div>
            <div class="result-bot">🌸 <span v-html="highlightKeyword(result.bot_reply)"></span></div>
          </div>
        </div>
      </div>
      <div v-else-if="searchKeyword && !searching" class="no-results">
        未找到匹配的对话
      </div>
    </div>

    <div class="character-selector">
      <div 
        v-for="char in characters" 
        :key="char.id"
        :class="['character-card', { selected: selectedCharacter === char.id }]"
        @click="selectCharacter(char)"
      >
        <div class="char-avatar">
          <img v-if="char.avatar_path" :src="`/api/avatar/${char.id}`" class="avatar-img" />
          <span v-else>🎭</span>
        </div>
        <span class="char-name">{{ char.name }}</span>
        <span v-if="char.api_config?.provider_type === 'openai_compatible'" class="api-badge">☁️</span>
      </div>
      <button class="btn btn-secondary btn-sm" @click="showApiConfig = !showApiConfig">
        {{ showApiConfig ? '收起' : '🔑 API配置' }}
      </button>
    </div>

    <div v-if="showApiConfig" class="api-config-panel">
      <div class="api-config-header">
        <span>🔑 当前角色 API 配置</span>
        <span class="api-hint">配置后使用云端模型替代本地模型</span>
      </div>
      <div class="api-config-body">
        <div class="api-field">
          <label>Provider 类型</label>
          <select v-model="apiConfig.provider_type" class="input-field" @change="onApiProviderChange">
            <option value="ollama">Ollama (本地)</option>
            <option value="openai_compatible">OpenAI 兼容 API</option>
          </select>
        </div>
        <template v-if="apiConfig.provider_type === 'openai_compatible'">
          <div class="api-field">
            <label>Base URL</label>
            <input v-model="apiConfig.base_url" type="text" class="input-field" placeholder="https://openrouter.ai/api/v1" />
          </div>
          <div class="api-field">
            <label>API Key</label>
            <input v-model="apiConfig.api_key" type="password" class="input-field" placeholder="sk-..." />
          </div>
          <div class="api-field">
            <label>模型名称</label>
            <input v-model="apiConfig.model_name" type="text" class="input-field" placeholder="google/gemma-3-1b-it:free" />
          </div>
        </template>
        <div class="api-actions">
          <button class="btn btn-secondary btn-sm" @click="testApiConnection" :disabled="testingApi">
            {{ testingApi ? '测试中...' : '🔍 测试连接' }}
          </button>
          <span v-if="apiTestResult" :class="['api-test-result', apiTestResult.success ? 'success' : 'error']">
            {{ apiTestResult.message }}
          </span>
          <button class="btn btn-primary btn-sm" @click="saveApiConfig" :disabled="savingApi">
            {{ savingApi ? '保存中...' : '💾 保存' }}
          </button>
        </div>
      </div>
    </div>

    <div class="chat-container">
      <div class="messages-area" ref="messagesRef">
        <div v-if="messages.length === 0" class="empty-state">
          <span class="empty-icon">🌸</span>
          <p>开始和三月七聊天吧！</p>
        </div>
        
        <div 
          v-for="(msg, index) in messages" 
          :key="index"
          :class="['message', msg.role]"
        >
          <div class="message-avatar" :class="msg.role">
            <img v-if="msg.role === 'user'" :src="userAvatar" class="avatar-img" />
            <img v-else :src="getCharacterAvatar(currentCharacter)" class="avatar-img" />
          </div>
          <div class="message-content" :class="{ 'streaming': msg.isStreaming }">
            <span class="text-content">{{ msg.content }}</span>
            <span v-if="msg.isStreaming" class="cursor">|</span>
          </div>
        </div>

        <div v-if="loading && !isStreamingMode" class="message bot loading-message">
          <div class="message-avatar bot">
            <img :src="getCharacterAvatar(currentCharacter)" class="avatar-img" />
          </div>
          <div class="message-content loading">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>

      <div class="input-area">
        <div class="streaming-toggle">
          <label class="toggle-label">
            <input 
              type="checkbox" 
              v-model="isStreamingMode"
              class="toggle-input"
            />
            <span class="toggle-slider"></span>
            <span class="toggle-text">流式传输</span>
          </label>
        </div>
        
        <textarea
          v-model="userInput"
          class="input-field message-input"
          placeholder="输入消息..."
          rows="3"
          @keydown.enter.exact.prevent="sendMessage"
          :disabled="loading"
        ></textarea>

        <div v-if="interimTranscript" class="interim-transcript">
          {{ interimTranscript }}...
        </div>

        <div class="waveform-container" v-if="isRecording || isPlayingAudio">
          <canvas ref="waveformCanvas" class="waveform-canvas"></canvas>
        </div>

        <div class="input-actions">
          <button
            v-if="voiceInputSupported"
            :class="['btn', 'btn-voice', { recording: isRecording }]"
            @click="isRecording ? stopVoiceInput() : startVoiceInput()"
            :disabled="loading"
            :title="isRecording ? '点击停止录音' : '点击开始语音输入'"
          >
            <span v-if="isRecording" class="voice-icon recording">🔴</span>
            <span v-else class="voice-icon">🎤</span>
          </button>

          <button
            class="btn btn-secondary"
            @click="clearHistory"
            :disabled="loading"
          >
            🗑️ 清除历史
          </button>
          <button
            class="btn btn-primary"
            @click="sendMessage"
            :disabled="loading || !userInput.trim()"
          >
            📨 发送
          </button>
        </div>
      </div>

      <div v-if="showAudioPlayer && currentAudio" class="audio-player">
        <audio 
          ref="audioPlayerRef"
          :src="currentAudio" 
          @ended="onAudioEnded"
          @timeupdate="onTimeUpdate"
          @loadedmetadata="onAudioLoaded"
          @play="audioIsPlaying = true"
          @pause="audioIsPlaying = false"
        ></audio>
        
        <div class="audio-controls">
          <button class="audio-btn" @click="toggleAudioPlay" :title="audioIsPlaying ? '暂停' : '播放'">
            <span v-if="audioIsPlaying">⏸️</span>
            <span v-else>▶️</span>
          </button>
          
          <div class="audio-progress-container">
            <div 
              class="audio-progress-bar"
              @click="seekAudio"
              @mousedown="startDragProgress"
              ref="progressBarRef"
            >
              <div class="audio-progress-bg"></div>
              <div class="audio-progress-fill" :style="{ width: audioProgress + '%' }"></div>
              <div class="audio-progress-thumb" :style="{ left: audioProgress + '%' }"></div>
            </div>
          </div>
          
          <div class="audio-time">
            <span>{{ formatAudioTime(audioCurrentTime) }}</span>
            <span class="audio-time-separator">/</span>
            <span>{{ formatAudioTime(audioDuration) }}</span>
          </div>
          
          <div class="audio-queue-info" v-if="audioQueue.length > 0">
            <span><img src="/emojis/三月七_biu.png" class="emoji-icon" /> {{ audioQueue.length }}</span>
          </div>
          
          <button class="audio-btn audio-close-btn" @click="closeAudioPlayer" title="关闭">
            ✖️
          </button>
        </div>
      </div>

      <div v-if="lastConversationId" class="rating-area">
        <span>为这次回复评分：</span>
        <div class="rating-stars">
          <button
            v-for="star in 5"
            :key="star"
            :class="['star-btn', { active: rating >= star }]"
            @click="rateConversation(star)"
            :disabled="ratingSubmitted"
          >
            ⭐
          </button>
        </div>
        <span v-if="ratingSubmitted" class="rating-done">✓ 已评分</span>
        
        <button class="btn btn-secondary btn-sm" @click="handleViewIterationSuggestions">
          🔍 查看修正建议
        </button>
        
        <button class="btn btn-secondary btn-sm" @click="toggleAnchors">
          <img src="/emojis/三月七_暗中观察.png" class="emoji-icon" /> 记忆锚点
        </button>
        
        <button class="btn btn-primary btn-sm" @click="updateRagKnowledge" :disabled="ragUpdating">
          <template v-if="ragUpdating">更新中...</template>
          <template v-else><img src="/emojis/三月七_吃糖.png" class="emoji-icon" /> 更新RAG知识</template>
        </button>
        
        <div class="export-area">
          <button class="btn btn-secondary btn-sm" @click="showExportMenu = !showExportMenu">
            📥 导出
          </button>
          <div v-if="showExportMenu" class="export-menu">
            <button class="export-option" @click="exportConversation('markdown')">
              Markdown
            </button>
            <button class="export-option" @click="exportConversation('json')">
              JSON
            </button>
          </div>
        </div>
      </div>

      <div v-if="showRagIteration" class="rag-iteration-panel">
        <div class="rag-header">
          <span>🔍 RAG 迭代修正建议</span>
          <button class="btn-close" @click="showRagIteration = false">×</button>
        </div>
        <div v-if="ragIterationLoading" class="rag-loading">
          加载中...
        </div>
        <div v-else-if="ragIterationResult" class="rag-content-wrapper">
          <div class="rag-content" v-html="ragIterationResult"></div>
          
          <div v-if="ragIterationEditing" class="rag-edit-area">
            <textarea 
              v-model="ragIterationEditedContent" 
              class="rag-edit-textarea"
              placeholder="编辑建议内容..."
            ></textarea>
          </div>
          
          <div class="rag-actions">
            <button 
              v-if="!ragIterationConfirmed"
              class="btn btn-primary btn-sm" 
              @click="confirmRagIteration" 
              :disabled="ragIterationLoading"
            >
              ✓ 确认
            </button>
            <button 
              v-if="!ragIterationConfirmed"
              class="btn btn-secondary btn-sm" 
              @click="toggleEditRagIteration" 
            >
              {{ ragIterationEditing ? '取消编辑' : '✏️ 编辑' }}
            </button>
            <button 
              class="btn btn-secondary btn-sm" 
              @click="regenerateRagIteration" 
              :disabled="ragIterationLoading"
            >
              🔄 重新生成
            </button>
            <span v-if="ragIterationConfirmed" class="rag-confirmed-hint">
              ✓ 已确认，可更新到RAG
            </span>
          </div>
        </div>
        <div v-else class="rag-empty">
          点击"查看修正建议"按钮获取分析结果
        </div>
      </div>

      <div v-if="showAnchors" class="anchors-panel">
        <div class="anchors-header">
          <span><img src="/emojis/三月七_暗中观察.png" class="emoji-icon" /> 记忆锚点管理</span>
          <button class="btn-close" @click="showAnchors = false">×</button>
        </div>
        <div class="anchors-add">
          <div class="anchors-add-row">
            <input
              v-model="newAnchorContent"
              type="text"
              class="input-field"
              placeholder="输入新的记忆锚点内容..."
              @keydown.enter="addAnchor"
            />
            <select v-model="newAnchorType" class="input-field anchor-type-select">
              <option value="manual">手动</option>
              <option value="important">重要事件</option>
              <option value="preference">用户偏好</option>
            </select>
            <button class="btn btn-primary btn-sm" @click="addAnchor" :disabled="!newAnchorContent.trim()">
              ➕ 添加
            </button>
          </div>
        </div>
        <div v-if="anchorsLoading" class="anchors-loading">加载中...</div>
        <div v-else-if="anchors.length === 0" class="anchors-empty">
          暂无记忆锚点，可手动添加
        </div>
        <div v-else class="anchors-list">
          <div v-for="anchor in anchors" :key="anchor.id" class="anchor-item">
            <div class="anchor-info">
              <span :class="['anchor-type-badge', anchor.anchor_type]">
                {{ anchor.anchor_type === 'manual' ? '手动' : anchor.anchor_type === 'important' ? '重要' : anchor.anchor_type === 'preference' ? '偏好' : anchor.anchor_type }}
              </span>
              <span class="anchor-content">{{ anchor.content }}</span>
            </div>
            <div class="anchor-meta">
              <span class="anchor-importance">重要度: {{ (anchor.importance * 100).toFixed(0) }}%</span>
              <button class="btn btn-danger btn-sm" @click="deleteAnchor(anchor.id)">🗑️</button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="feedbackMessage" class="feedback-message" :class="feedbackMessageType">
        {{ feedbackMessage }}
      </div>
    </div>
    </div>

    <div v-if="showSessionContextMenu" class="context-menu" :style="contextMenuStyle">
      <button class="context-menu-item" @click="deleteSessionAction">
        🗑️ 删除会话
      </button>
    </div>

    <div v-if="showFeedbackModal" class="modal-overlay" @click.self="closeFeedbackModal">
      <div class="modal-content">
        <div class="modal-header">
          <span>选择问题类型</span>
          <button class="btn-close" @click="closeFeedbackModal">×</button>
        </div>
        <div class="modal-body">
          <p class="modal-hint">请选择您遇到的问题类型：</p>
          <div class="feedback-options">
            <button class="btn btn-feedback-option" @click="submitFeedbackWithRating('fact_error')">
              ❌ 事实不符
            </button>
            <button class="btn btn-feedback-option" @click="submitFeedbackWithRating('role_deviation')">
              <img src="/emojis/三月七_无语.png" class="emoji-icon" /> 偏离角色
            </button>
            <button class="btn btn-feedback-option" @click="submitFeedbackWithRating('history_forget')">
              <img src="/emojis/三月七_无语.png" class="emoji-icon" /> 遗忘历史
            </button>
            <button class="btn btn-feedback-option" @click="submitFeedbackWithRating('think_leak')">
              <img src="/emojis/三月七_无语.png" class="emoji-icon" /> 思考泄露
            </button>
          </div>
          <button class="btn btn-secondary btn-skip" @click="skipFeedback">
            跳过，仅提交评分
          </button>
        </div>
      </div>
    </div>

    <div v-if="showIterationApiWarning" class="modal-overlay" @click.self="showIterationApiWarning = false">
      <div class="modal-content">
        <div class="modal-header">
          <span>⚠️ 迭代分析提示</span>
          <button class="btn-close" @click="showIterationApiWarning = false">×</button>
        </div>
        <div class="modal-body">
          <p class="modal-hint">使用本地模型进行迭代分析效果有限，建议配置专用迭代 API（如 OpenRouter 免费模型）以获得更好的分析结果</p>
          <div class="iteration-warning-actions">
            <button class="btn btn-primary" @click="goToCharactersPage">
              🔧 前往配置
            </button>
            <button class="btn btn-secondary" @click="continueIterationAnyway">
              仍然继续
            </button>
          </div>
        </div>
      </div>
    </div>

    <HistoryPanel 
      :isOpen="showHistory" 
      @close="showHistory = false"
      @select="restoreConversation"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, onUnmounted, watch } from 'vue'
import api from '../utils/api'
import HistoryPanel from '../components/HistoryPanel.vue'

const characters = ref([])
const selectedCharacter = ref(null)
const messages = ref([])
const userInput = ref('')
const loading = ref(false)
const currentAudio = ref(null)
const lastConversationId = ref(null)
const rating = ref(4)
const ratingSubmitted = ref(false)
const showExportMenu = ref(false)
const messagesRef = ref(null)
const audioPlayerRef = ref(null)
const progressBarRef = ref(null)
const showHistory = ref(false)

const isStreamingMode = ref(true)
const audioQueue = ref([])
const isPlayingAudio = ref(false)

const audioIsPlaying = ref(false)
const audioCurrentTime = ref(0)
const audioDuration = ref(0)
const audioProgress = ref(0)
const isDraggingProgress = ref(false)
const showAudioPlayer = ref(false)

const isRecording = ref(false)
const recognition = ref(null)
const voiceInputSupported = ref(false)
const interimTranscript = ref('')
let eventSource = null
let reconnectAttempts = 0
const maxReconnectAttempts = 3

const showSearch = ref(false)
const searchKeyword = ref('')
const searchResults = ref([])
const searching = ref(false)

const feedbackSubmitting = ref(false)
const feedbackMessage = ref('')
const feedbackMessageType = ref('success')

const showRagIteration = ref(false)
const ragIterationLoading = ref(false)
const ragIterationResult = ref('')
const ragIterationHasExisting = ref(false)
const ragIterationExistingTime = ref(null)
const lastFeedbackType = ref('general')
const ragIterationFeedbackId = ref(null)
const ragIterationConfirmed = ref(false)
const ragIterationEditing = ref(false)
const ragIterationEditedContent = ref('')

const showAnchors = ref(false)
const anchors = ref([])
const anchorsLoading = ref(false)
const newAnchorContent = ref('')
const newAnchorType = ref('manual')

const waveformCanvas = ref(null)
let audioContext = null
let analyser = null
let animationId = null

const showApiConfig = ref(false)
const apiConfig = ref({
  provider_type: 'ollama',
  base_url: '',
  api_key: '',
  model_name: ''
})
const testingApi = ref(false)
const apiTestResult = ref(null)
const savingApi = ref(false)

const sidebarCollapsed = ref(false)
const sessions = ref([])
const sessionsLoading = ref(false)
const currentSessionId = ref(null)
const showSessionContextMenu = ref(false)
const contextMenuStyle = ref({})
const selectedSessionForMenu = ref(null)

const showFeedbackModal = ref(false)
const pendingRating = ref(0)
const ragUpdating = ref(false)

const showIterationApiWarning = ref(false)
const iterationApiWarningPending = ref(false)

const editingSessionId = ref(null)
const editingTitle = ref('')
const userProfile = ref(null)

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

  try {
    const profileResp = await api.get('/user/profile')
    if (profileResp.success) {
      userProfile.value = profileResp.profile || profileResp
    }
  } catch (e) {
    console.error('Failed to load user profile:', e)
  }

  await loadSessions()

  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    recognition.value = new SpeechRecognition()
    recognition.value.continuous = false
    recognition.value.interimResults = true
    recognition.value.lang = 'zh-CN'

    recognition.value.onstart = () => {
      isRecording.value = true
      interimTranscript.value = ''
      startAudioVisualization()
    }

    recognition.value.onresult = (event) => {
      let interim = ''
      let final = ''

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          final += transcript
        } else {
          interim += transcript
        }
      }

      interimTranscript.value = interim

      if (final) {
        userInput.value = final.trim()
        interimTranscript.value = ''
      }
    }

    recognition.value.onerror = (event) => {
      console.error('Speech recognition error:', event.error)
      isRecording.value = false
      interimTranscript.value = ''
      stopAudioVisualization()

      if (event.error === 'not-allowed') {
        alert('请允许使用麦克风以启用语音输入')
      }
    }

    recognition.value.onend = () => {
      if (isRecording.value) {
        isRecording.value = false
        stopAudioVisualization()
        if (userInput.value.trim()) {
          sendMessage()
        }
      }
      interimTranscript.value = ''
    }

    voiceInputSupported.value = true
  }

  document.addEventListener('click', closeContextMenu)
})

onUnmounted(() => {
  closeEventSource()
  stopAudioVisualization()
  document.removeEventListener('click', closeContextMenu)
})

function selectCharacter(char) {
  selectedCharacter.value = char.id
  apiConfig.value = {
    provider_type: char.api_config?.provider_type || 'ollama',
    base_url: char.api_config?.base_url || '',
    api_key: '',
    model_name: char.api_config?.model_name || ''
  }
  apiTestResult.value = null
}

function onApiProviderChange() {
  if (apiConfig.value.provider_type === 'openai_compatible' && !apiConfig.value.base_url) {
    apiConfig.value.base_url = 'https://openrouter.ai/api/v1'
  }
  apiTestResult.value = null
}

async function testApiConnection() {
  if (apiConfig.value.provider_type === 'openai_compatible') {
    if (!apiConfig.value.base_url || !apiConfig.value.api_key || !apiConfig.value.model_name) {
      apiTestResult.value = { success: false, message: '请填写完整配置' }
      return
    }
  }
  testingApi.value = true
  apiTestResult.value = null
  try {
    const response = await api.post('/llm/test', {
      provider_type: apiConfig.value.provider_type,
      base_url: apiConfig.value.base_url,
      api_key: apiConfig.value.api_key,
      model_name: apiConfig.value.model_name
    })
    if (response.success && response.test_result?.success) {
      apiTestResult.value = { success: true, message: `连接成功! 延迟: ${response.test_result.latency_ms}ms` }
    } else {
      apiTestResult.value = { success: false, message: response.test_result?.message || '连接失败' }
    }
  } catch (e) {
    apiTestResult.value = { success: false, message: e.detail || e.message || '测试失败' }
  } finally {
    testingApi.value = false
  }
}

async function saveApiConfig() {
  if (!selectedCharacter.value) return
  savingApi.value = true
  try {
    await api.put(`/characters/${selectedCharacter.value}/api-config`, {
      provider_type: apiConfig.value.provider_type,
      base_url: apiConfig.value.base_url,
      api_key: apiConfig.value.api_key,
      model_name: apiConfig.value.model_name
    })
    const charIndex = characters.value.findIndex(c => c.id === selectedCharacter.value)
    if (charIndex !== -1) {
      characters.value[charIndex].api_config = { ...apiConfig.value }
    }
    feedbackMessage.value = '✅ API 配置已保存'
    feedbackMessageType.value = 'success'
    setTimeout(() => { feedbackMessage.value = '' }, 3000)
  } catch (e) {
    feedbackMessage.value = '❌ 保存失败: ' + (e.detail || '未知错误')
    feedbackMessageType.value = 'error'
  } finally {
    savingApi.value = false
  }
}

function closeEventSource() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

async function startAudioVisualization() {
  try {
    audioContext = new (window.AudioContext || window.webkitAudioContext)()
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const microphone = audioContext.createMediaStreamSource(stream)
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 2048
    microphone.connect(analyser)
    drawWaveform()
  } catch (e) {
    console.error('Audio visualization error:', e)
  }
}

function stopAudioVisualization() {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close()
    audioContext = null
  }
  analyser = null
  drawIdleWaveform()
}

function drawWaveform() {
  if (!analyser || !waveformCanvas.value) return
  
  const canvas = waveformCanvas.value
  const ctx = canvas.getContext('2d')
  const bufferLength = analyser.frequencyBinCount
  const dataArray = new Uint8Array(bufferLength)
  analyser.getByteTimeDomainData(dataArray)
  
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.lineWidth = 2
  ctx.strokeStyle = '#ff6b9d'
  ctx.shadowColor = '#e94560'
  ctx.shadowBlur = 4
  ctx.beginPath()
  
  const sliceWidth = canvas.width / bufferLength
  let x = 0
  
  for (let i = 0; i < bufferLength; i++) {
    const v = dataArray[i] / 128.0
    const y = v * canvas.height / 2
    if (i === 0) {
      ctx.moveTo(x, y)
    } else {
      ctx.lineTo(x, y)
    }
    x += sliceWidth
  }
  
  ctx.lineTo(canvas.width, canvas.height / 2)
  ctx.stroke()
  ctx.shadowBlur = 0
  
  animationId = requestAnimationFrame(drawWaveform)
}

function drawIdleWaveform() {
  if (!waveformCanvas.value) return
  
  const canvas = waveformCanvas.value
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.lineWidth = 1.5
  ctx.strokeStyle = 'rgba(255,107,157,0.3)'
  ctx.beginPath()
  ctx.moveTo(0, canvas.height / 2)
  ctx.lineTo(canvas.width, canvas.height / 2)
  ctx.stroke()
}

function startVoiceInput() {
  if (!voiceInputSupported.value || !recognition.value) {
    alert('抱歉，您的浏览器不支持语音输入。请使用 Chrome 或 Edge 浏览器。')
    return
  }

  if (isRecording.value) {
    return
  }

  try {
    interimTranscript.value = ''
    recognition.value.start()
  } catch (e) {
    console.error('Failed to start voice recognition:', e)
  }
}

function stopVoiceInput() {
  if (!recognition.value || !isRecording.value) {
    return
  }

  try {
    recognition.value.stop()
  } catch (e) {
    console.error('Failed to stop voice recognition:', e)
  }
}

function connectSSE(message) {
  closeEventSource()
  
  const token = localStorage.getItem('token') || ''
  const params = new URLSearchParams({
    message: message,
    token: token,
    character_id: selectedCharacter.value || '',
    session_id: currentSessionId.value || ''
  })
  
  const baseUrl = api.defaults?.baseURL || ''
  const url = `${baseUrl}/api/chat/stream?${params.toString()}`
  
  eventSource = new EventSource(url)
  
  let currentMessageIndex = messages.value.length - 1
  
  eventSource.onopen = () => {
    reconnectAttempts = 0
  }
  
  eventSource.addEventListener('text', (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.content) {
        if (messages.value[currentMessageIndex]) {
          messages.value[currentMessageIndex].content += data.content
          messages.value[currentMessageIndex].isStreaming = true
        }
        scrollToBottom()
      }
    } catch (e) {
      console.error('Failed to parse text event:', e)
    }
  })
  
  eventSource.addEventListener('audio', (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.audio) {
        const audioUrl = `data:audio/wav;base64,${data.audio}`
        audioQueue.value.push(audioUrl)
        
        if (!isPlayingAudio.value) {
          playNextAudio()
        }
      }
    } catch (e) {
      console.error('Failed to parse audio event:', e)
    }
  })
  
  eventSource.addEventListener('done', (event) => {
    try {
      const data = JSON.parse(event.data)
      if (messages.value[currentMessageIndex]) {
        messages.value[currentMessageIndex].isStreaming = false
      }
      lastConversationId.value = data.conversation_id
      if (data.session_id && !currentSessionId.value) {
        currentSessionId.value = data.session_id
        loadSessions()
      }
      loading.value = false
      closeEventSource()
    } catch (e) {
      console.error('Failed to parse done event:', e)
    }
  })
  
  eventSource.addEventListener('error', (event) => {
    try {
      const data = JSON.parse(event.data)
      if (messages.value[currentMessageIndex]) {
        messages.value[currentMessageIndex].content = `错误: ${data.message || '流式传输失败'}`
        messages.value[currentMessageIndex].isStreaming = false
      }
      loading.value = false
      closeEventSource()
    } catch (e) {
      console.error('Failed to parse error event:', e)
    }
  })
  
  eventSource.onerror = (error) => {
    console.error('EventSource error:', error)
    
    if (reconnectAttempts < maxReconnectAttempts) {
      reconnectAttempts++
      console.log(`尝试重连 (${reconnectAttempts}/${maxReconnectAttempts})...`)
      setTimeout(() => {
        connectSSE(message)
      }, 1000 * reconnectAttempts)
    } else {
      if (messages.value[currentMessageIndex]) {
        messages.value[currentMessageIndex].content = '错误: 连接失败，请重试'
        messages.value[currentMessageIndex].isStreaming = false
      }
      loading.value = false
      closeEventSource()
    }
  }
}

async function playNextAudio() {
  if (audioQueue.value.length === 0) {
    isPlayingAudio.value = false
    currentAudio.value = null
    showAudioPlayer.value = false
    return
  }
  
  isPlayingAudio.value = true
  currentAudio.value = audioQueue.value.shift()
  showAudioPlayer.value = true
  
  await nextTick()
  
  if (audioPlayerRef.value) {
    try {
      await audioPlayerRef.value.play()
    } catch (e) {
      console.error('Failed to play audio:', e)
      playNextAudio()
    }
  }
}

function onAudioEnded() {
  if (audioQueue.value.length > 0) {
    playNextAudio()
  } else {
    audioIsPlaying.value = false
    isPlayingAudio.value = false
  }
}

function onTimeUpdate() {
  if (!audioPlayerRef.value || isDraggingProgress.value) return
  
  audioCurrentTime.value = audioPlayerRef.value.currentTime
  if (audioPlayerRef.value.duration) {
    audioProgress.value = (audioCurrentTime.value / audioPlayerRef.value.duration) * 100
  }
}

function onAudioLoaded() {
  if (audioPlayerRef.value) {
    audioDuration.value = audioPlayerRef.value.duration
  }
}

function toggleAudioPlay() {
  if (!audioPlayerRef.value) return
  
  if (audioIsPlaying.value) {
    audioPlayerRef.value.pause()
  } else {
    audioPlayerRef.value.play()
  }
}

function seekAudio(event) {
  if (!audioPlayerRef.value || !progressBarRef.value) return
  
  const rect = progressBarRef.value.getBoundingClientRect()
  const clickX = event.clientX - rect.left
  const percentage = clickX / rect.width
  const newTime = percentage * audioPlayerRef.value.duration
  
  audioPlayerRef.value.currentTime = newTime
  audioCurrentTime.value = newTime
  audioProgress.value = percentage * 100
}

function startDragProgress(event) {
  isDraggingProgress.value = true
  
  const onMouseMove = (e) => {
    if (!progressBarRef.value) return
    
    const rect = progressBarRef.value.getBoundingClientRect()
    const clickX = Math.max(0, Math.min(e.clientX - rect.left, rect.width))
    const percentage = clickX / rect.width
    
    audioProgress.value = percentage * 100
    if (audioPlayerRef.value && audioPlayerRef.value.duration) {
      audioCurrentTime.value = percentage * audioPlayerRef.value.duration
    }
  }
  
  const onMouseUp = (e) => {
    isDraggingProgress.value = false
    
    if (audioPlayerRef.value && progressBarRef.value) {
      const rect = progressBarRef.value.getBoundingClientRect()
      const clickX = Math.max(0, Math.min(e.clientX - rect.left, rect.width))
      const percentage = clickX / rect.width
      
      audioPlayerRef.value.currentTime = percentage * audioPlayerRef.value.duration
      audioProgress.value = percentage * 100
    }
    
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }
  
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

function closeAudioPlayer() {
  if (audioPlayerRef.value) {
    audioPlayerRef.value.pause()
  }
  
  showAudioPlayer.value = false
  currentAudio.value = null
  audioQueue.value = []
  isPlayingAudio.value = false
  audioIsPlaying.value = false
  audioCurrentTime.value = 0
  audioDuration.value = 0
  audioProgress.value = 0
}

function formatAudioTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00'
  
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

async function sendMessage() {
  if (!userInput.value.trim() || loading.value) return
  
  const message = userInput.value.trim()
  messages.value.push({ role: 'user', content: message })
  userInput.value = ''
  loading.value = true
  lastConversationId.value = null
  ratingSubmitted.value = false
  audioQueue.value = []
  isPlayingAudio.value = false
  currentAudio.value = null
  showAudioPlayer.value = false
  audioCurrentTime.value = 0
  audioDuration.value = 0
  audioProgress.value = 0
  audioIsPlaying.value = false
  showRagIteration.value = false
  ragIterationResult.value = ''
  
  await nextTick()
  scrollToBottom()
  
  if (isStreamingMode.value) {
    messages.value.push({ role: 'bot', content: '', isStreaming: true })
    await nextTick()
    scrollToBottom()
    connectSSE(message)
  } else {
    try {
      const response = await api.post('/chat', {
        message,
        character_id: selectedCharacter.value,
        session_id: currentSessionId.value
      })
      
      if (response.success) {
        messages.value.push({ role: 'bot', content: response.response })
        lastConversationId.value = response.conversation_id
        if (response.session_id && !currentSessionId.value) {
          currentSessionId.value = response.session_id
          await loadSessions()
        }
        
        if (response.audio) {
          currentAudio.value = `data:audio/wav;base64,${response.audio}`
          showAudioPlayer.value = true
          await nextTick()
          if (audioPlayerRef.value) {
            try {
              await audioPlayerRef.value.play()
            } catch (e) {
              console.error('Failed to play audio:', e)
            }
          }
        }
      }
    } catch (e) {
      messages.value.push({ role: 'bot', content: `错误: ${e.detail || '请求失败'}` })
    } finally {
      loading.value = false
      await nextTick()
      scrollToBottom()
    }
  }
}

async function clearHistory() {
  try {
    await api.post('/chat/clear')
    messages.value = []
    currentAudio.value = null
    lastConversationId.value = null
    ratingSubmitted.value = false
    audioQueue.value = []
    isPlayingAudio.value = false
    showAudioPlayer.value = false
    audioCurrentTime.value = 0
    audioDuration.value = 0
    audioProgress.value = 0
    audioIsPlaying.value = false
    showRagIteration.value = false
    ragIterationResult.value = ''
    closeEventSource()
  } catch (e) {
    console.error('Failed to clear history:', e)
  }
}

async function rateConversation(star) {
  if (!lastConversationId.value || ratingSubmitted.value) return

  try {
    await api.post('/chat/rating', {
      conversation_id: lastConversationId.value,
      rating: star
    })
    rating.value = star
    ratingSubmitted.value = true

    if (star <= 3) {
      pendingRating.value = star
      showFeedbackModal.value = true
    } else {
      feedbackMessage.value = '✅ 评分已提交，感谢您的反馈！'
      feedbackMessageType.value = 'success'
      setTimeout(() => { feedbackMessage.value = '' }, 3000)
    }
  } catch (e) {
    console.error('Failed to submit rating:', e)
  }
}

function closeFeedbackModal() {
  showFeedbackModal.value = false
  pendingRating.value = 0
}

async function submitFeedbackWithRating(feedbackType) {
  if (!lastConversationId.value) return
  
  feedbackSubmitting.value = true
  lastFeedbackType.value = feedbackType
  
  try {
    const feedbackResponse = await api.post('/chat/feedback', {
      conversation_id: lastConversationId.value,
      feedback_type: feedbackType
    })

    if (feedbackResponse.timeout) {
      feedbackMessage.value = '⏱️ RAG迭代分析超时，API响应时间过长，请稍后重试'
      feedbackMessageType.value = 'error'
      closeFeedbackModal()
      setTimeout(() => { feedbackMessage.value = '' }, 5000)
      return
    }
    
    const labels = {
      fact_error: '事实不符',
      role_deviation: '偏离角色',
      history_forget: '遗忘历史',
      think_leak: '思考泄露'
    }
    
    feedbackMessage.value = `✅ 反馈「${labels[feedbackType]}」已提交，感谢您的反馈！`
    feedbackMessageType.value = 'success'
    
    closeFeedbackModal()
    
    setTimeout(() => {
      feedbackMessage.value = ''
    }, 3000)
  } catch (e) {
    feedbackMessage.value = `❌ 反馈保存失败: ${e.detail || '未知错误'}`
    feedbackMessageType.value = 'error'
  } finally {
    feedbackSubmitting.value = false
  }
}

function skipFeedback() {
  feedbackMessage.value = '✅ 评分已提交，感谢您的反馈！'
  feedbackMessageType.value = 'success'
  closeFeedbackModal()
  setTimeout(() => { feedbackMessage.value = '' }, 3000)
}

async function submitFeedback(feedbackType) {
  if (!lastConversationId.value) return
  
  feedbackSubmitting.value = true
  lastFeedbackType.value = feedbackType
  
  try {
    await api.post('/chat/feedback', {
      conversation_id: lastConversationId.value,
      feedback_type: feedbackType
    })
    
    const labels = {
      fact_error: '事实不符',
      role_deviation: '偏离角色',
      history_forget: '遗忘历史',
      think_leak: '思考泄露'
    }
    
    feedbackMessage.value = `✅ 负面反馈「${labels[feedbackType]}」已保存`
    feedbackMessageType.value = 'success'
    
    setTimeout(() => {
      feedbackMessage.value = ''
    }, 3000)
  } catch (e) {
    feedbackMessage.value = `❌ 反馈保存失败: ${e.detail || '未知错误'}`
    feedbackMessageType.value = 'error'
  } finally {
    feedbackSubmitting.value = false
  }
}

async function fetchRagIteration(forceRegenerate = false) {
  if (!lastConversationId.value) return
  
  ragIterationLoading.value = true
  ragIterationEditing.value = false
  ragIterationEditedContent.value = ''
  
  try {
    if (!forceRegenerate) {
      const existingResponse = await api.get(`/rag/iteration/${lastConversationId.value}`)
      if (existingResponse.success && existingResponse.has_result) {
        const result = existingResponse.result
        ragIterationHasExisting.value = true
        ragIterationExistingTime.value = result.created_at
        ragIterationFeedbackId.value = result.id
        ragIterationConfirmed.value = result.confirmed || false
        
        let analysis
        try {
          analysis = JSON.parse(result.correction_suggestion)
        } catch {
          analysis = result.correction_suggestion
        }
        
        ragIterationEditedContent.value = typeof analysis === 'object' 
          ? JSON.stringify(analysis, null, 2) 
          : String(analysis)
        
        let html = '<div class="rag-analysis">'
        html += `<div class="rag-existing-hint">📄 已保存的分析结果 (${new Date(result.created_at).toLocaleString()})${ragIterationConfirmed.value ? ' ✓ 已确认' : ''}</div>`
        if (typeof analysis === 'object') {
          if (analysis.auto_detected && analysis.analyses) {
            html += `<div class="rag-auto-detected">🔍 自动检测到 ${Object.keys(analysis.analyses).length} 个潜在问题</div>`
            for (const [type, item] of Object.entries(analysis.analyses)) {
              html += `<div class="rag-item"><strong>${type}</strong>: ${formatAnalysisResult(item)}</div>`
            }
          } else {
            for (const [key, val] of Object.entries(analysis)) {
              html += `<div class="rag-item"><strong>${key}</strong>: ${formatAnalysisResult(val)}</div>`
            }
          }
        } else {
          html += analysis
        }
        html += '</div>'
        ragIterationResult.value = html
        ragIterationLoading.value = false
        return
      }
    }
    
    ragIterationHasExisting.value = false
    ragIterationResult.value = ''
    ragIterationConfirmed.value = false
    
    const response = await api.post('/rag/iteration', {
      conversation_id: lastConversationId.value,
      feedback_type: lastFeedbackType.value
    })
    
    if (!response.success && response.error === 'iteration_api_not_configured') {
      ragIterationLoading.value = false
      showRagIteration.value = false
      showIterationApiWarning.value = true
      return
    }

    if (response.timeout) {
      ragIterationResult.value = '<div class="rag-timeout-error">⏱️ RAG迭代分析超时，API响应时间过长，请稍后重试</div>'
      ragIterationLoading.value = false
      return
    }

    if (response.feedback_id) {
      ragIterationFeedbackId.value = response.feedback_id
    }
    
    if (response.analysis) {
      ragIterationEditedContent.value = typeof response.analysis === 'object' 
        ? JSON.stringify(response.analysis, null, 2) 
        : String(response.analysis)
      
      let html = '<div class="rag-analysis">'
      html += '<div class="rag-new-hint">✨ 新生成的分析结果</div>'
      if (typeof response.analysis === 'object') {
        if (response.analysis.api_error || response.analysis.error) {
          html += `<div class="rag-api-error">⚠️ API 错误: ${response.analysis.error || '未知错误'}</div>`
          html += '<div class="rag-error-hint">请稍后重试，或检查 API 配置是否正确。</div>'
        } else if (response.analysis.parse_error) {
          html += '<div class="rag-parse-error">⚠️ 解析错误: LLM 返回的格式无法识别</div>'
          html += `<div class="rag-raw-response">${response.analysis.raw_response || ''}</div>`
        } else if (response.analysis.auto_detected && response.analysis.analyses) {
          html += `<div class="rag-auto-detected">🔍 自动检测到 ${Object.keys(response.analysis.analyses).length} 个潜在问题</div>`
          for (const [type, analysis] of Object.entries(response.analysis.analyses)) {
            html += `<div class="rag-item"><strong>${type}</strong>: ${formatAnalysisResult(analysis)}</div>`
          }
        } else {
          for (const [key, val] of Object.entries(response.analysis)) {
            html += `<div class="rag-item"><strong>${key}</strong>: ${formatAnalysisResult(val)}</div>`
          }
        }
      } else {
        html += response.analysis
      }
      html += '</div>'
      ragIterationResult.value = html
    }
  } catch (e) {
    ragIterationResult.value = `<div class="rag-error">请求失败: ${e.detail || '未知错误'}</div>`
  } finally {
    ragIterationLoading.value = false
  }
}

async function regenerateRagIteration() {
  ragIterationHasExisting.value = false
  ragIterationResult.value = ''
  ragIterationConfirmed.value = false
  ragIterationFeedbackId.value = null
  await fetchRagIteration(true)
}

async function confirmRagIteration() {
  if (!ragIterationFeedbackId.value) return
  
  try {
    const response = await api.post('/rag/iteration/edit-confirm', {
      feedback_detail_id: ragIterationFeedbackId.value,
      edited_suggestion: ragIterationEditing.value ? ragIterationEditedContent.value : null
    })
    
    if (response.success) {
      ragIterationConfirmed.value = true
      ragIterationEditing.value = false
    }
  } catch (e) {
    console.error('确认失败:', e)
  }
}

function toggleEditRagIteration() {
  ragIterationEditing.value = !ragIterationEditing.value
}

function handleViewIterationSuggestions() {
  if (showRagIteration.value) {
    showRagIteration.value = false
    return
  }
  if (isIterationApiOllama.value) {
    showIterationApiWarning.value = true
    iterationApiWarningPending.value = true
    return
  }
  showRagIteration.value = true
}

function goToCharactersPage() {
  showIterationApiWarning.value = false
  iterationApiWarningPending.value = false
  window.location.hash = '/characters'
}

function continueIterationAnyway() {
  showIterationApiWarning.value = false
  if (iterationApiWarningPending.value) {
    iterationApiWarningPending.value = false
    showRagIteration.value = true
  }
}

function formatAnalysisResult(analysis) {
  if (typeof analysis === 'string') return analysis
  if (typeof analysis !== 'object') return String(analysis)
  
  let result = ''
  for (const [key, value] of Object.entries(analysis)) {
    if (Array.isArray(value)) {
      result += `<div class="analysis-array"><em>${key}</em>:<ul>`
      for (const item of value) {
        if (typeof item === 'object') {
          result += '<li>' + Object.entries(item).map(([k, v]) => `${k}: ${v}`).join(', ') + '</li>'
        } else {
          result += `<li>${item}</li>`
        }
      }
      result += '</ul></div>'
    } else if (typeof value === 'object') {
      result += `<div class="analysis-object"><em>${key}</em>: ${JSON.stringify(value)}</div>`
    } else {
      result += `<div class="analysis-item"><em>${key}</em>: ${value}</div>`
    }
  }
  return result
}

watch(showRagIteration, (newVal) => {
  if (newVal && !ragIterationResult.value) {
    fetchRagIteration()
  }
})

function toggleAnchors() {
  showAnchors.value = !showAnchors.value
  if (showAnchors.value) {
    loadAnchors()
  }
}

async function loadAnchors() {
  if (!selectedCharacter.value) return
  anchorsLoading.value = true
  try {
    const response = await api.get(`/memory/anchors/${selectedCharacter.value}`)
    if (response.success) {
      anchors.value = response.anchors || []
    }
  } catch (e) {
    console.error('Failed to load anchors:', e)
  } finally {
    anchorsLoading.value = false
  }
}

async function addAnchor() {
  if (!newAnchorContent.value.trim() || !selectedCharacter.value) return
  try {
    const response = await api.post('/memory/anchors', {
      character_id: selectedCharacter.value,
      content: newAnchorContent.value.trim(),
      anchor_type: newAnchorType.value,
      importance: 0.7
    })
    if (response.success) {
      newAnchorContent.value = ''
      await loadAnchors()
    }
  } catch (e) {
    console.error('Failed to add anchor:', e)
  }
}

async function deleteAnchor(anchorId) {
  if (!confirm('确定要删除此记忆锚点吗？')) return
  try {
    await api.delete(`/memory/anchors/${anchorId}`)
    await loadAnchors()
  } catch (e) {
    console.error('Failed to delete anchor:', e)
  }
}

async function updateRagKnowledge() {
  ragUpdating.value = true
  try {
    const response = await api.post('/rag/update')
    if (response.success) {
      feedbackMessage.value = `✅ RAG知识库更新成功！已更新 ${response.updated_count || 0} 条知识`
      feedbackMessageType.value = 'success'
    } else {
      feedbackMessage.value = '❌ 更新失败: ' + (response.message || '未知错误')
      feedbackMessageType.value = 'error'
    }
  } catch (e) {
    feedbackMessage.value = '❌ 更新失败: ' + (e.detail || e.message || '未知错误')
    feedbackMessageType.value = 'error'
  } finally {
    ragUpdating.value = false
    setTimeout(() => { feedbackMessage.value = '' }, 3000)
  }
}

async function searchHistory() {
  if (!searchKeyword.value.trim()) return
  
  searching.value = true
  searchResults.value = []
  
  try {
    const response = await api.get('/chat/search', {
      keyword: searchKeyword.value.trim()
    })
    
    if (response.success) {
      searchResults.value = response.results || []
    }
  } catch (e) {
    console.error('Failed to search history:', e)
  } finally {
    searching.value = false
  }
}

function clearSearch() {
  searchKeyword.value = ''
  searchResults.value = []
  showSearch.value = false
}

function highlightKeyword(text) {
  if (!text || !searchKeyword.value.trim()) return escapeHtml(text || '')
  const escaped = escapeHtml(text)
  const keyword = searchKeyword.value.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${keyword})`, 'gi')
  return escaped.replace(regex, '<mark class="search-highlight">$1</mark>')
}

function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function restoreSearchResult(result) {
  messages.value = [
    { role: 'user', content: result.user_input },
    { role: 'bot', content: result.bot_reply }
  ]
  lastConversationId.value = result.id
  
  if (result.rating) {
    rating.value = result.rating
    ratingSubmitted.value = true
  } else {
    ratingSubmitted.value = false
  }
  
  showSearch.value = false
  searchResults.value = []
  searchKeyword.value = ''
  
  nextTick(() => scrollToBottom())
}

function formatTime(timestamp) {
  if (!timestamp) return '-'
  return timestamp.replace('T', ' ').substring(0, 19)
}

async function exportConversation(format) {
  if (!lastConversationId.value) return

  showExportMenu.value = false

  try {
    const response = await api.get(`/conversations/${lastConversationId.value}/export?format=${format}`)

    if (response.success) {
      let fileContent
      let mimeType

      if (format === 'json') {
        fileContent = JSON.stringify(response.content, null, 2)
        mimeType = 'application/json'
      } else {
        fileContent = response.content
        mimeType = 'text/markdown'
      }

      const blob = new Blob([fileContent], { type: mimeType })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = response.filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }
  } catch (e) {
    console.error('Failed to export conversation:', e)
  }
}

function scrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

async function restoreConversation(conv) {
  showHistory.value = false
  console.log('[Chat] restoreConversation called:', conv)
  console.log('[Chat] session_id:', conv.session_id)
  
  if (conv.session_id) {
    try {
      console.log('[Chat] Loading session:', conv.session_id)
      const response = await api.get(`/sessions/${conv.session_id}`)
      console.log('[Chat] Session response:', response)
      if (response.success && response.messages) {
        console.log('[Chat] Messages count:', response.messages.length)
        messages.value = []
        for (const msg of response.messages) {
          messages.value.push({ role: 'user', content: msg.user_input })
          messages.value.push({ role: 'bot', content: msg.bot_reply })
        }
        lastConversationId.value = response.messages.length > 0 ? response.messages[response.messages.length - 1].id : null
        currentSessionId.value = conv.session_id
        console.log('[Chat] Restored messages:', messages.value.length)
      } else {
        console.log('[Chat] No messages in session or failed response')
      }
    } catch (e) {
      console.error('[Chat] Failed to load session:', e)
      messages.value = [
        { role: 'user', content: conv.user_input },
        { role: 'bot', content: conv.bot_reply }
      ]
      lastConversationId.value = conv.id
    }
  } else {
    console.log('[Chat] No session_id, showing single conversation')
    messages.value = [
      { role: 'user', content: conv.user_input },
      { role: 'bot', content: conv.bot_reply }
    ]
    lastConversationId.value = conv.id
  }
  
  if (conv.rating) {
    rating.value = conv.rating
    ratingSubmitted.value = true
  } else {
    ratingSubmitted.value = false
  }
  
  await nextTick()
  scrollToBottom()
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    const response = await api.get('/sessions')
    if (response.success) {
      sessions.value = response.sessions || []
    }
  } catch (e) {
    console.error('Failed to load sessions:', e)
  } finally {
    sessionsLoading.value = false
  }
}

function getCharacterName(characterId) {
  const char = characters.value.find(c => c.id === characterId)
  return char ? char.name : characterId || '未知角色'
}

function getSessionSummary(session) {
  if (session.title) {
    return session.title.length > 30 ? session.title.substring(0, 30) + '...' : session.title
  }
  if (session.last_message) {
    const msg = session.last_message.length > 30 ? session.last_message.substring(0, 30) + '...' : session.last_message
    return msg
  }
  return '新会话'
}

const userAvatar = computed(() => {
  return userProfile.value?.avatar || '/emojis/三月七_暗中观察.png'
})

const currentCharacter = computed(() => {
  return characters.value.find(c => c.id === selectedCharacter.value) || null
})

const isIterationApiOllama = computed(() => {
  const char = currentCharacter.value
  if (!char) return true
  const iterConfig = char.iteration_api_config
  if (iterConfig && iterConfig.provider_type !== 'ollama') {
    return !iterConfig.has_api_key
  }
  const mainConfig = char.api_config
  if (mainConfig && mainConfig.provider_type !== 'ollama') {
    return !mainConfig.has_api_key
  }
  return true
})

function getCharacterAvatar(char) {
  if (!char || !char.id) return '/emojis/三月七_开心.png'
  if (char.avatar_path) return `/api/avatar/${char.id}`
  return '/emojis/三月七_开心.png'
}

function startEditTitle(session) {
  editingSessionId.value = session.id
  editingTitle.value = session.title || getSessionSummary(session)
}

async function saveSessionTitle(session) {
  if (editingSessionId.value === null) return
  const title = editingTitle.value.trim()
  if (title && title !== session.title) {
    try {
      await api.put(`/chat/sessions/${session.id}/title`, { title })
      session.title = title
    } catch (e) {
      console.error('Failed to update title:', e)
    }
  }
  editingSessionId.value = null
  editingTitle.value = ''
}

function formatSessionTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  if (diff < 604800000) return Math.floor(diff / 86400000) + '天前'
  
  return timestamp.replace('T', ' ').substring(0, 10)
}

async function createNewSession() {
  if (!selectedCharacter.value) return
  
  try {
    const response = await api.post('/sessions', {
      character_id: selectedCharacter.value
    })
    
    if (response.success) {
      currentSessionId.value = response.session_id
      messages.value = []
      lastConversationId.value = null
      ratingSubmitted.value = false
      await loadSessions()
    }
  } catch (e) {
    console.error('Failed to create session:', e)
  }
}

async function switchSession(session) {
  if (currentSessionId.value === session.id) return
  
  try {
    const response = await api.get(`/sessions/${session.id}`)
    
    if (response.success) {
      currentSessionId.value = session.id
      selectedCharacter.value = session.character_id
      
      const restoreResponse = await api.post(`/sessions/${session.id}/restore`)
      
      if (restoreResponse.success) {
        messages.value = []
        const sessionMessages = response.messages || []
        
        for (const msg of sessionMessages) {
          messages.value.push({ role: 'user', content: msg.user_input })
          messages.value.push({ role: 'bot', content: msg.bot_reply })
        }
        
        if (sessionMessages.length > 0) {
          const lastMsg = sessionMessages[sessionMessages.length - 1]
          lastConversationId.value = lastMsg.id
          if (lastMsg.rating) {
            rating.value = lastMsg.rating
            ratingSubmitted.value = true
          } else {
            ratingSubmitted.value = false
          }
        }
        
        await nextTick()
        scrollToBottom()
      }
    }
  } catch (e) {
    console.error('Failed to switch session:', e)
  }
}

function showSessionMenu(event, session) {
  event.preventDefault()
  selectedSessionForMenu.value = session
  showSessionContextMenu.value = true
  contextMenuStyle.value = {
    top: `${event.clientY}px`,
    left: `${event.clientX}px`
  }
}

function closeContextMenu() {
  showSessionContextMenu.value = false
  selectedSessionForMenu.value = null
}

async function deleteSessionAction() {
  if (!selectedSessionForMenu.value) return
  
  const session = selectedSessionForMenu.value
  if (!confirm(`确定要删除这个会话吗？\n角色: ${getCharacterName(session.character_id)}\n消息数: ${session.message_count || 0}`)) {
    closeContextMenu()
    return
  }
  
  try {
    await api.delete(`/sessions/${session.id}`)
    
    if (currentSessionId.value === session.id) {
      currentSessionId.value = null
      messages.value = []
      lastConversationId.value = null
      ratingSubmitted.value = false
    }
    
    await loadSessions()
    closeContextMenu()
  } catch (e) {
    console.error('Failed to delete session:', e)
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
.chat-page {
  height: 100%;
  display: flex;
  padding: 24px;
  overflow: hidden;
  gap: 16px;
}

.session-sidebar {
  width: 280px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  flex-shrink: 0;
}

.session-sidebar.collapsed {
  width: 40px;
}

.sidebar-header {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
  font-weight: 500;
}

.btn-collapse {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px 8px;
  font-size: 14px;
}

.btn-collapse:hover {
  color: var(--accent-primary);
}

.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.btn-new-session {
  margin: 12px;
  flex-shrink: 0;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-loading,
.session-empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 20px;
}

.session-item {
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: var(--accent-primary);
}

.session-item.active {
  background: rgba(233, 69, 96, 0.15);
  border-color: var(--accent-primary);
}

.session-char-name {
  font-weight: 500;
  margin-bottom: 4px;
  color: var(--text-primary);
}

.session-summary {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-title-edit .title-input {
  width: 100%;
  background: rgba(255,255,255,0.1);
  border: 1px solid var(--accent-primary);
  border-radius: 4px;
  color: var(--text-primary);
  padding: 2px 6px;
  font-size: 13px;
  outline: none;
}

.edit-title-btn {
  opacity: 0;
  margin-left: 4px;
  cursor: pointer;
  font-size: 11px;
}

.session-item:hover .edit-title-btn {
  opacity: 0.6;
}

.edit-title-btn:hover {
  opacity: 1 !important;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-secondary);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.page-header p {
  color: var(--text-secondary);
  margin-top: 8px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.history-btn {
  padding: 10px 20px;
}

.header-left {
  flex: 1;
}

.search-panel {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
}

.search-input-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.search-input-row .input-field {
  flex: 1;
}

.search-results {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.search-result-item {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.search-result-item:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--accent-primary);
}

.api-badge {
  font-size: 12px;
  margin-left: 4px;
}

.api-config-panel {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  margin-bottom: 20px;
  overflow: hidden;
}

.api-config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: rgba(233, 69, 96, 0.1);
  font-weight: 500;
}

.api-hint {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: normal;
}

.api-config-body {
  padding: 18px;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}

.api-field {
  flex: 1;
  min-width: 200px;
}

.api-field label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.api-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding-top: 8px;
}

.api-test-result {
  font-size: 13px;
}

.api-test-result.success {
  color: #81c784;
}

.api-test-result.error {
  color: #f44336;
}

.result-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.result-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.result-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.result-user,
.result-bot {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.no-results {
  text-align: center;
  color: var(--text-secondary);
  padding: 20px;
}

:deep(.search-highlight) {
  background: rgba(233, 69, 96, 0.4);
  color: #fff;
  border-radius: 2px;
  padding: 0 2px;
}

.character-selector {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.character-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 2px solid var(--border-color);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.character-card:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--accent-primary);
  transform: translateY(-2px);
}

.character-card.selected {
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.3) 0%, rgba(255, 107, 157, 0.2) 100%);
  border-color: var(--accent-primary);
}

.char-avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.char-name {
  font-weight: 500;
}

.chat-container {
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
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-state {
  flex: 1;
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

.message {
  display: flex;
  gap: 12px;
  max-width: 70%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.bot {
  align-self: flex-start;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
}

.message.user .message-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.message.bot .message-avatar {
  background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
}

.message-content {
  padding: 14px 18px;
  border-radius: 18px;
  line-height: 1.6;
  word-break: break-word;
}

.message.user .message-content {
  background: var(--user-bubble);
  color: white;
  border-bottom-right-radius: 6px;
}

.message.bot .message-content {
  background: var(--bot-bubble);
  color: var(--text-primary);
  border-bottom-left-radius: 6px;
  border: 1px solid var(--border-color);
}

.message-content.streaming {
  position: relative;
}

.message-content .text-content {
  display: inline;
}

.cursor {
  display: inline-block;
  margin-left: 2px;
  font-weight: bold;
  color: var(--accent-primary);
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% {
    opacity: 1;
  }
  51%, 100% {
    opacity: 0;
  }
}

.loading-message .message-content.loading {
  display: flex;
  gap: 6px;
  padding: 16px 24px;
}

.dot {
  width: 8px;
  height: 8px;
  background: var(--accent-secondary);
  border-radius: 50%;
  animation: pulse 1.5s infinite;
}

.dot:nth-child(2) {
  animation-delay: 0.3s;
}

.dot:nth-child(3) {
  animation-delay: 0.6s;
}

.input-area {
  padding: 16px;
  background: rgba(0, 0, 0, 0.3);
  border-top: 1px solid var(--border-color);
}

.streaming-toggle {
  margin-bottom: 12px;
}

.toggle-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.toggle-input {
  display: none;
}

.toggle-slider {
  position: relative;
  width: 44px;
  height: 24px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.toggle-slider::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  transition: all 0.3s ease;
}

.toggle-input:checked + .toggle-slider {
  background: var(--accent-primary);
}

.toggle-input:checked + .toggle-slider::after {
  left: 22px;
}

.toggle-text {
  font-size: 14px;
  color: var(--text-secondary);
}

.message-input {
  resize: none;
  min-height: 80px;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
}

.interim-transcript {
  margin-top: 8px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-secondary);
  font-style: italic;
}

.waveform-container {
  margin-top: 12px;
}

.waveform-canvas {
  width: 100%;
  height: 60px;
  border-radius: 8px;
  background: rgba(233, 69, 96, 0.05);
}

.btn-voice {
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.1);
  border: 2px solid var(--border-color);
  border-radius: 50%;
  transition: all 0.3s ease;
}

.btn-voice:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.2);
  border-color: var(--accent-primary);
}

.btn-voice.recording {
  background: rgba(255, 69, 58, 0.3);
  border-color: #ff3b30;
  animation: pulse-recording 1.5s infinite;
}

.btn-voice:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.voice-icon {
  font-size: 18px;
}

.voice-icon.recording {
  animation: pulse-dot 1s infinite;
}

@keyframes pulse-recording {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(255, 59, 48, 0.4);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(255, 59, 48, 0);
  }
}

@keyframes pulse-dot {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.8;
  }
}

.audio-player {
  padding: 12px 16px;
  background: rgba(233, 69, 96, 0.1);
  border-top: 1px solid var(--border-color);
}

.audio-player audio {
  display: none;
}

.audio-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.audio-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  padding: 8px;
  border-radius: 50%;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.audio-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: scale(1.1);
}

.audio-close-btn {
  opacity: 0.6;
}

.audio-close-btn:hover {
  opacity: 1;
}

.audio-progress-container {
  flex: 1;
  padding: 0 8px;
}

.audio-progress-bar {
  position: relative;
  height: 24px;
  display: flex;
  align-items: center;
  cursor: pointer;
}

.audio-progress-bg {
  position: absolute;
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}

.audio-progress-fill {
  position: absolute;
  height: 6px;
  background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
  border-radius: 3px;
  transition: width 0.1s linear;
}

.audio-progress-thumb {
  position: absolute;
  width: 14px;
  height: 14px;
  background: #fff;
  border-radius: 50%;
  transform: translateX(-50%);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
  transition: transform 0.1s ease;
}

.audio-progress-bar:hover .audio-progress-thumb {
  transform: translateX(-50%) scale(1.2);
}

.audio-time {
  font-size: 13px;
  color: var(--text-secondary);
  min-width: 80px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.audio-time-separator {
  margin: 0 2px;
}

.audio-queue-info {
  font-size: 12px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.1);
  padding: 4px 8px;
  border-radius: 12px;
}

.rating-area {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(255, 193, 7, 0.1);
  border-top: 1px solid var(--border-color);
}

.rating-stars {
  display: flex;
  gap: 4px;
}

.star-btn {
  background: none;
  font-size: 24px;
  opacity: 0.4;
  transition: all 0.2s ease;
}

.star-btn:hover,
.star-btn.active {
  opacity: 1;
  transform: scale(1.2);
}

.rating-done {
  color: #81c784;
  font-weight: 500;
}

.feedback-section {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 12px;
  padding-left: 12px;
  border-left: 1px solid var(--border-color);
}

.feedback-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.btn-feedback {
  padding: 6px 12px;
  font-size: 12px;
  background: rgba(255, 82, 82, 0.15);
  border: 1px solid rgba(255, 82, 82, 0.3);
  color: #ff6b6b;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.btn-feedback:hover:not(:disabled) {
  background: rgba(255, 82, 82, 0.25);
  border-color: rgba(255, 82, 82, 0.5);
}

.btn-feedback:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.export-area {
  position: relative;
  margin-left: auto;
}

.export-menu {
  position: absolute;
  bottom: 100%;
  right: 0;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 10;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.export-option {
  background: none;
  border: none;
  padding: 8px 16px;
  color: var(--text-primary);
  cursor: pointer;
  border-radius: 6px;
  font-size: 14px;
  text-align: left;
  transition: background 0.2s ease;
}

.export-option:hover {
  background: rgba(233, 69, 96, 0.2);
}

.rag-iteration-panel {
  padding: 16px;
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid var(--border-color);
  max-height: 300px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.rag-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 500;
  color: var(--accent-secondary);
  flex-shrink: 0;
}

.btn-close {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 20px;
  cursor: pointer;
  padding: 4px 8px;
}

.rag-loading {
  color: var(--text-secondary);
  text-align: center;
  padding: 20px;
}

.rag-content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.rag-content {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 12px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  word-wrap: break-word;
}

.rag-actions {
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.rag-edit-area {
  margin-top: 12px;
}

.rag-edit-textarea {
  width: 100%;
  min-height: 150px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: var(--text-primary);
  font-family: monospace;
  font-size: 12px;
  resize: vertical;
}

.rag-edit-textarea:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.rag-confirmed-hint {
  color: #81c784;
  font-size: 12px;
  padding: 4px 8px;
  background: rgba(129, 199, 132, 0.1);
  border-radius: 4px;
}

.rag-existing-hint {
  color: var(--accent-secondary);
  font-size: 12px;
  margin-bottom: 8px;
  padding: 4px 8px;
  background: rgba(129, 199, 132, 0.1);
  border-radius: 4px;
}

.rag-new-hint {
  color: var(--accent-primary);
  font-size: 12px;
  margin-bottom: 8px;
  padding: 4px 8px;
  background: rgba(233, 69, 96, 0.1);
  border-radius: 4px;
}

.rag-empty {
  color: var(--text-secondary);
  text-align: center;
  padding: 20px;
}

.rag-error {
  color: #ff6b6b;
  padding: 12px;
}

.rag-timeout-error {
  color: #ffa726;
  padding: 16px;
  background: rgba(255, 167, 38, 0.1);
  border-radius: 8px;
  text-align: center;
  font-size: 14px;
}

.rag-api-error {
  color: #ff6b6b;
  padding: 12px;
  background: rgba(255, 107, 107, 0.1);
  border-radius: 8px;
  margin-bottom: 8px;
}

.rag-error-hint {
  color: var(--text-secondary);
  font-size: 12px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
}

.rag-parse-error {
  color: #ffa726;
  padding: 12px;
  background: rgba(255, 167, 38, 0.1);
  border-radius: 8px;
  margin-bottom: 8px;
}

.rag-raw-response {
  font-family: monospace;
  font-size: 12px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}

.anchors-panel {
  padding: 16px;
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid var(--border-color);
}

.anchors-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 500;
  color: var(--accent-secondary);
}

.anchors-add {
  margin-bottom: 12px;
}

.anchors-add-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.anchors-add-row .input-field {
  flex: 1;
}

.anchor-type-select {
  width: 120px;
  flex: none !important;
}

.anchors-loading,
.anchors-empty {
  color: var(--text-secondary);
  text-align: center;
  padding: 16px;
}

.anchors-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.anchor-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  gap: 10px;
}

.anchor-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.anchor-type-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.anchor-type-badge.manual {
  background: rgba(33, 150, 243, 0.2);
  color: #64b5f6;
}

.anchor-type-badge.important {
  background: rgba(233, 69, 96, 0.2);
  color: var(--accent-secondary);
}

.anchor-type-badge.preference {
  background: rgba(129, 199, 132, 0.2);
  color: #81c784;
}

.anchor-type-badge.auto {
  background: rgba(255, 193, 7, 0.2);
  color: #ffd54f;
}

.anchor-content {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.anchor-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.anchor-importance {
  font-size: 11px;
  color: var(--text-secondary);
}

.feedback-message {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  z-index: 1000;
  animation: slideUp 0.3s ease;
}

.feedback-message.success {
  background: rgba(129, 199, 132, 0.9);
  color: #fff;
}

.feedback-message.error {
  background: rgba(255, 107, 107, 0.9);
  color: #fff;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

.btn-sm {
  padding: 8px 16px;
  font-size: 13px;
}

.context-menu {
  position: fixed;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 8px;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.context-menu-item {
  display: block;
  width: 100%;
  background: none;
  border: none;
  padding: 8px 16px;
  color: var(--text-primary);
  cursor: pointer;
  border-radius: 6px;
  font-size: 14px;
  text-align: left;
  transition: background 0.2s ease;
}

.context-menu-item:hover {
  background: rgba(233, 69, 96, 0.2);
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  width: 400px;
  max-width: 90%;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  font-weight: 500;
}

.modal-body {
  padding: 20px;
}

.modal-hint {
  color: var(--text-secondary);
  margin-bottom: 16px;
}

.feedback-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}

.btn-feedback-option {
  padding: 12px 16px;
  font-size: 14px;
  background: rgba(255, 82, 82, 0.1);
  border: 1px solid rgba(255, 82, 82, 0.3);
  color: var(--text-primary);
  border-radius: 8px;
  transition: all 0.2s ease;
  text-align: left;
}

.btn-feedback-option:hover {
  background: rgba(255, 82, 82, 0.2);
  border-color: rgba(255, 82, 82, 0.5);
}

.btn-skip {
  width: 100%;
}

.iteration-warning-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 8px;
}
</style>

<style>
.rag-content::-webkit-scrollbar {
  width: 8px;
}

.rag-content::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

.rag-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.3);
  border-radius: 4px;
}

.rag-content::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.5);
}
</style>
