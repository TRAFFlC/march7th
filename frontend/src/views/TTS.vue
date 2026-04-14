<template>
  <div class="tts-page">
    <div class="page-header">
      <h1 class="title"><img src="/emojis/三月七_悄悄话.png" class="emoji-icon-lg" /> TTS 独立测试</h1>
      <p>单独测试文本转语音功能</p>
    </div>

    <div class="tts-container">
      <div class="tts-main">
        <div class="form-group">
          <label>输入文本</label>
          <textarea 
            v-model="textInput"
            class="input-field"
            placeholder="输入要转换为语音的文本..."
            rows="6"
          ></textarea>
        </div>

        <div class="form-group">
          <label>语速: {{ speed }}</label>
          <input type="range" v-model="speed" min="0.5" max="2" step="0.1" />
        </div>

        <div class="form-group">
          <label>情绪参考音频</label>
          <div class="emotion-buttons">
            <button
              v-for="emo in emotions"
              :key="emo.value"
              :class="['emotion-btn', { active: selectedEmotion === emo.value }]"
              @click="selectedEmotion = emo.value"
            >
              {{ emo.icon }} {{ emo.label }}
            </button>
          </div>
        </div>

        <div class="action-buttons">
          <button 
            class="btn btn-primary"
            @click="synthesize"
            :disabled="loading || !textInput.trim()"
          >
            <template v-if="loading">生成中...</template>
            <template v-else><img src="/emojis/三月七_悄悄话.png" class="emoji-icon" /> 生成语音</template>
          </button>
          <button 
            class="btn btn-secondary"
            @click="quickTest"
            :disabled="loading"
          >
            <img src="/emojis/三月七_biu.png" class="emoji-icon" /> 快速测试
          </button>
        </div>

        <div v-if="audioUrl" class="audio-result">
          <h3><img src="/emojis/三月七_悄悄话.png" class="emoji-icon" /> 生成结果</h3>
          <audio :src="audioUrl" controls></audio>
          <div v-if="synthesisStats" class="synthesis-stats">
            <div class="stat-item">
              <span class="stat-label">合成耗时</span>
              <span class="stat-value">{{ synthesisStats.time }}s</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">音频大小</span>
              <span class="stat-value">{{ synthesisStats.size }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">文本长度</span>
              <span class="stat-value">{{ synthesisStats.textLength }}字</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">速度比</span>
              <span class="stat-value">{{ synthesisStats.ratio }}</span>
            </div>
          </div>
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>
      </div>

      <div class="tts-sidebar">
        <div class="tts-info">
          <h3><img src="/emojis/三月七_盯.png" class="emoji-icon" /> 当前情绪参考音频</h3>
          <div class="info-item">
            <span>当前情绪:</span>
            <span>{{ emotions.find(e => e.value === selectedEmotion)?.icon }} {{ emotions.find(e => e.value === selectedEmotion)?.label || selectedEmotion }}</span>
          </div>
          <div class="info-item">
            <span>参考音频:</span>
            <span>{{ currentEmotionInfo.audioPath }}</span>
          </div>
          <div class="info-item">
            <span>参考文本:</span>
            <span>{{ currentEmotionInfo.refText }}</span>
          </div>
        </div>

        <div class="tts-info">
          <h3><img src="/emojis/三月七_买买买.png" class="emoji-icon" /> 默认TTS配置</h3>
          <div class="info-item">
            <span>GPT权重:</span>
            <span>{{ refConfig.gpt_weight?.split('/').pop() || '未配置' }}</span>
          </div>
          <div class="info-item">
            <span>SoVITS权重:</span>
            <span>{{ refConfig.sovits_weight?.split('/').pop() || '未配置' }}</span>
          </div>
          <div class="info-item">
            <span>TTS端口:</span>
            <span>{{ refConfig.port || 9880 }}</span>
          </div>
        </div>

        <div class="emotion-test-section">
          <h3><img src="/emojis/三月七_开心.png" class="emoji-icon" /> 情绪快速切换测试</h3>
          <p class="section-hint">快速测试不同情绪参考音频的合成效果</p>
          <div class="emotion-test-grid">
            <button
              v-for="emo in emotions"
              :key="emo.value"
              class="emotion-test-btn"
              @click="testEmotion(emo.value)"
              :disabled="loading"
              :class="{ active: lastTestedEmotion === emo.value }"
            >
              <span class="emo-icon">{{ emo.icon }}</span>
              <span class="emo-label">{{ emo.label }}</span>
            </button>
          </div>
          <div v-if="emotionTestResult" class="emotion-test-result">
            <div class="emo-result-header">
              <span>{{ emotionTestResult.emotion }} 测试结果</span>
              <span class="emo-result-time">{{ emotionTestResult.time }}s</span>
            </div>
            <audio v-if="emotionTestResult.audio" :src="emotionTestResult.audio" controls></audio>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../utils/api'

const textInput = ref('')
const speed = ref(1.0)
const loading = ref(false)
const audioUrl = ref(null)
const error = ref('')
const refConfig = ref({})
const selectedEmotion = ref('neutral')
const synthesisStats = ref(null)
const lastTestedEmotion = ref(null)
const emotionTestResult = ref(null)
const emotionConfig = ref({})

const emotions = [
  { value: 'neutral', label: '平静', icon: '😐' },
  { value: 'happy', label: '开心', icon: '😊' },
  { value: 'confused', label: '困惑', icon: '😕' },
  { value: 'sad', label: '悲伤', icon: '😢' },
  { value: 'angry', label: '生气', icon: '😠' },
  { value: 'excited', label: '兴奋', icon: '🤩' }
]

const currentEmotionInfo = computed(() => {
  const config = emotionConfig.value[selectedEmotion.value]
  if (!config || !config.ref_audio_path) {
    return {
      audioPath: '未配置',
      refText: '未配置'
    }
  }
  const pathParts = config.ref_audio_path.split('/')
  const fileName = pathParts[pathParts.length - 1] || config.ref_audio_path
  return {
    audioPath: fileName,
    refText: config.ref_text ? (config.ref_text.length > 50 ? config.ref_text.substring(0, 50) + '...' : config.ref_text) : '未配置'
  }
})

onMounted(async () => {
  try {
    const [configResponse, emotionResponse] = await Promise.all([
      api.get('/tts/config'),
      api.get('/tts/emotion-config')
    ])
    if (configResponse.success) {
      refConfig.value = configResponse.config
    }
    if (emotionResponse.success) {
      emotionConfig.value = emotionResponse.emotions
    }
  } catch (e) {
    console.error('Failed to load TTS config:', e)
  }
})

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

async function synthesize() {
  if (!textInput.value.trim() || loading.value) return
  
  loading.value = true
  error.value = ''
  audioUrl.value = null
  synthesisStats.value = null
  
  const startTime = performance.now()
  const textLength = textInput.value.trim().length
  
  try {
    const response = await api.get('/tts', {
      text: textInput.value.trim(),
      speed: speed.value,
      emotion: selectedEmotion.value
    })
    
    const elapsed = ((performance.now() - startTime) / 1000).toFixed(2)
    
    if (response.success && response.audio) {
      audioUrl.value = `data:audio/wav;base64,${response.audio}`
      const audioSize = Math.ceil((response.audio.length * 3) / 4)
      synthesisStats.value = {
        time: elapsed,
        size: formatBytes(audioSize),
        textLength,
        ratio: (textLength / parseFloat(elapsed)).toFixed(1) + ' 字/秒'
      }
    } else {
      error.value = '语音合成失败'
    }
  } catch (e) {
    error.value = e.detail || '请求失败'
  } finally {
    loading.value = false
  }
}

async function quickTest() {
  loading.value = true
  error.value = ''
  audioUrl.value = null
  synthesisStats.value = null
  
  const testText = '你好，这是一段快速测试文本。'
  textInput.value = testText
  
  const startTime = performance.now()
  
  try {
    const response = await api.get('/tts', {
      text: testText,
      speed: 1.0,
      emotion: selectedEmotion.value
    })
    
    const elapsed = ((performance.now() - startTime) / 1000).toFixed(2)
    
    if (response.success && response.audio) {
      audioUrl.value = `data:audio/wav;base64,${response.audio}`
      const audioSize = Math.ceil((response.audio.length * 3) / 4)
      synthesisStats.value = {
        time: elapsed,
        size: formatBytes(audioSize),
        textLength: testText.length,
        ratio: (testText.length / parseFloat(elapsed)).toFixed(1) + ' 字/秒'
      }
    } else {
      error.value = '快速测试失败：TTS 服务不可用'
    }
  } catch (e) {
    error.value = '快速测试失败：' + (e.detail || '请求失败')
  } finally {
    loading.value = false
  }
}

async function testEmotion(emotion) {
  loading.value = true
  lastTestedEmotion.value = emotion
  emotionTestResult.value = null
  
  const testText = '这是一段情绪测试文本。'
  const startTime = performance.now()
  
  try {
    const response = await api.get('/tts', {
      text: testText,
      speed: 1.0,
      emotion: emotion
    })
    
    const elapsed = ((performance.now() - startTime) / 1000).toFixed(2)
    
    if (response.success && response.audio) {
      const emo = emotions.find(e => e.value === emotion)
      emotionTestResult.value = {
        emotion: emo ? `${emo.icon} ${emo.label}` : emotion,
        time: elapsed,
        audio: `data:audio/wav;base64,${response.audio}`
      }
    }
  } catch (e) {
    console.error('Emotion test failed:', e)
  } finally {
    loading.value = false
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
.tts-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow-y: auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header p {
  color: var(--text-secondary);
  margin-top: 8px;
}

.tts-container {
  flex: 1;
  display: flex;
  gap: 20px;
}

.tts-main {
  flex: 1;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 24px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  color: var(--accent-secondary);
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 10px;
}

.form-group textarea {
  resize: none;
}

.form-group input[type="range"] {
  width: 100%;
}

.emotion-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.emotion-btn {
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s ease;
}

.emotion-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--accent-primary);
}

.emotion-btn.active {
  background: rgba(233, 69, 96, 0.2);
  border-color: var(--accent-primary);
  color: var(--accent-secondary);
}

.action-buttons {
  margin-top: 24px;
  display: flex;
  gap: 12px;
}

.audio-result {
  margin-top: 24px;
  padding: 20px;
  background: rgba(233, 69, 96, 0.1);
  border-radius: 12px;
}

.audio-result h3 {
  color: var(--accent-secondary);
  margin-bottom: 16px;
}

.audio-result audio {
  width: 100%;
}

.synthesis-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.stat-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--accent-secondary);
  font-family: 'JetBrains Mono', monospace;
}

.error-message {
  margin-top: 16px;
  padding: 12px;
  background: rgba(255, 82, 82, 0.15);
  border: 1px solid rgba(255, 82, 82, 0.4);
  border-radius: 10px;
  color: #ff6b6b;
}

.tts-sidebar {
  width: 340px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.tts-info {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 20px;
}

.tts-info h3 {
  color: var(--accent-secondary);
  margin-bottom: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-color);
}

.info-item:last-child {
  border-bottom: none;
}

.info-item span:first-child {
  color: var(--text-secondary);
  font-size: 13px;
  margin-bottom: 4px;
}

.info-item span:last-child {
  color: var(--text-primary);
  font-size: 14px;
  word-break: break-all;
}

.emotion-test-section {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 20px;
}

.emotion-test-section h3 {
  color: var(--accent-secondary);
  margin-bottom: 4px;
}

.section-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 16px 0;
}

.emotion-test-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.emotion-test-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.emotion-test-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--accent-primary);
}

.emotion-test-btn.active {
  background: rgba(233, 69, 96, 0.2);
  border-color: var(--accent-primary);
  color: var(--accent-secondary);
}

.emotion-test-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.emo-icon {
  font-size: 20px;
}

.emo-label {
  font-size: 11px;
}

.emotion-test-result {
  margin-top: 12px;
  padding: 12px;
  background: rgba(233, 69, 96, 0.1);
  border-radius: 8px;
}

.emo-result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--accent-secondary);
}

.emo-result-time {
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-secondary);
}

.emotion-test-result audio {
  width: 100%;
  height: 36px;
}
</style>
