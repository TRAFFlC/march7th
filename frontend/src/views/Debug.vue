<template>
  <div class="debug-page">
    <div class="page-header">
      <h1 class="title"><img src="/emojis/三月七_吃糖.png" class="emoji-icon-lg" /> 调试面板</h1>
      <p>查看系统调试信息</p>
    </div>

    <div class="debug-content-wrapper">
      <div class="tab-header">
        <h3>🔧 调试信息面板</h3>
        <button class="btn btn-secondary" @click="loadDebugInfo">
          🔄 刷新
        </button>
      </div>

      <div v-if="!debugInfo" class="empty-state">
        <p>暂无调试信息，请先进行一次对话</p>
      </div>

      <div v-else class="debug-content">
        <div class="debug-section">
          <div class="section-header" @click="toggleSection('llm')">
            <span><img src="/emojis/三月七_biu.png" class="emoji-icon" /> LLM 设置</span>
            <span class="toggle-icon">{{ expandedSections.llm ? '▼' : '▶' }}</span>
          </div>
          <div v-if="expandedSections.llm" class="section-content">
            <div class="info-grid">
              <div class="info-item">
                <label>模型:</label>
                <span>{{ debugInfo.model_name || debugInfo.llm?.model || '-' }}</span>
              </div>
              <div class="info-item">
                <label>Temperature:</label>
                <span>{{ debugInfo.temperature || '-' }}</span>
              </div>
              <div class="info-item">
                <label>Top P:</label>
                <span>{{ debugInfo.top_p || '-' }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="debug-section">
          <div class="section-header" @click="toggleSection('tokens')">
            <span>📊 Token 使用</span>
            <span class="toggle-icon">{{ expandedSections.tokens ? '▼' : '▶' }}</span>
          </div>
          <div v-if="expandedSections.tokens" class="section-content">
            <div class="info-grid">
              <div class="info-item highlight">
                <label>输入 Tokens:</label>
                <span>{{ debugInfo.llm?.input_tokens || debugInfo.input_tokens || '-' }}</span>
              </div>
              <div class="info-item highlight">
                <label>输出 Tokens:</label>
                <span>{{ debugInfo.llm?.output_tokens || debugInfo.output_tokens || '-' }}</span>
              </div>
              <div class="info-item highlight">
                <label>总 Tokens:</label>
                <span>{{ (debugInfo.llm?.input_tokens || 0) + (debugInfo.llm?.output_tokens || 0) || ((debugInfo.input_tokens || 0) + (debugInfo.output_tokens || 0)) || '-' }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="debug-section">
          <div class="section-header" @click="toggleSection('prompt')">
            <span><img src="/emojis/三月七_吃糖.png" class="emoji-icon" /> 完整 Prompt</span>
            <span class="toggle-icon">{{ expandedSections.prompt ? '▼' : '▶' }}</span>
          </div>
          <div v-if="expandedSections.prompt" class="section-content">
            <div class="json-viewer">
              <pre>{{ formatJson(debugInfo.llm?.full_prompt || debugInfo.full_prompt) }}</pre>
            </div>
          </div>
        </div>

        <div class="debug-section">
          <div class="section-header" @click="toggleSection('rag')">
            <span><img src="/emojis/三月七_吃糖.png" class="emoji-icon" /> RAG 检索结果</span>
            <span class="toggle-icon">{{ expandedSections.rag ? '▼' : '▶' }}</span>
          </div>
          <div v-if="expandedSections.rag" class="section-content">
            <div v-if="!hasRagResults()" class="empty-section">无 RAG 数据</div>
            <div v-else class="rag-list">
              <div v-for="(doc, index) in getRagDocuments()" :key="index" class="rag-item">
                <div class="rag-header">
                  <span class="rag-index">文档 {{ index + 1 }}</span>
                  <span class="rag-score">分数: {{ doc.score || doc.distance || '-' }}</span>
                </div>
                <div class="rag-content">{{ doc.content || doc.text || doc }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="debug-section">
          <div class="section-header" @click="toggleSection('tts')">
            <span><img src="/emojis/三月七_悄悄话.png" class="emoji-icon" /> TTS 合成信息</span>
            <span class="toggle-icon">{{ expandedSections.tts ? '▼' : '▶' }}</span>
          </div>
          <div v-if="expandedSections.tts" class="section-content">
            <div class="info-grid">
              <div class="info-item">
                <label>合成时间:</label>
                <span>{{ debugInfo.tts?.synthesis_time ? debugInfo.tts.synthesis_time + 's' : '-' }}</span>
              </div>
              <div class="info-item">
                <label>音频大小:</label>
                <span>{{ debugInfo.tts?.audio_size_bytes ? formatBytes(debugInfo.tts.audio_size_bytes) : '-' }}</span>
              </div>
            </div>
            <div v-if="debugInfo.tts?.text" class="tts-text">
              <label>合成文本:</label>
              <pre>{{ debugInfo.tts.text }}</pre>
            </div>
          </div>
        </div>

        <div class="debug-section">
          <div class="section-header" @click="toggleSection('timing')">
            <span><img src="/emojis/三月七_困.png" class="emoji-icon" /> 时间统计</span>
            <span class="toggle-icon">{{ expandedSections.timing ? '▼' : '▶' }}</span>
          </div>
          <div v-if="expandedSections.timing" class="section-content">
            <div class="info-grid">
              <div class="info-item">
                <label>LLM 生成时间:</label>
                <span>{{ debugInfo.llm?.generation_time ? debugInfo.llm.generation_time + 's' : '-' }}</span>
              </div>
              <div class="info-item">
                <label>TTS 合成时间:</label>
                <span>{{ debugInfo.tts?.synthesis_time ? debugInfo.tts.synthesis_time + 's' : '-' }}</span>
              </div>
              <div class="info-item highlight">
                <label>总耗时:</label>
                <span>{{ debugInfo.total_time ? debugInfo.total_time + 's' : '-' }}</span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="debugInfo.timestamp" class="debug-footer">
          <span>最后更新: {{ debugInfo.timestamp }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../utils/api'

const debugInfo = ref(null)
const expandedSections = ref({
  llm: true,
  tokens: true,
  prompt: false,
  rag: true,
  tts: true,
  timing: true,
})

onMounted(() => {
  loadDebugInfo()
})

async function loadDebugInfo() {
  try {
    const response = await api.get('/debug-info')
    if (response.success) {
      debugInfo.value = response.debug_info
    }
  } catch (e) {
    console.error('Failed to load debug info:', e)
  }
}

function toggleSection(section) {
  expandedSections.value[section] = !expandedSections.value[section]
}

function formatJson(obj) {
  if (!obj) return '-'
  if (typeof obj === 'string') {
    try {
      return JSON.stringify(JSON.parse(obj), null, 2)
    } catch {
      return obj
    }
  }
  return JSON.stringify(obj, null, 2)
}

function hasRagResults() {
  if (!debugInfo.value) return false
  const rag = debugInfo.value.rag || debugInfo.value.llm?.rag || debugInfo.value.rag_documents
  if (!rag) return false
  if (Array.isArray(rag)) return rag.length > 0
  if (rag.documents) return rag.documents.length > 0
  return false
}

function getRagDocuments() {
  if (!debugInfo.value) return []
  const rag = debugInfo.value.rag || debugInfo.value.llm?.rag || debugInfo.value.rag_documents
  if (!rag) return []
  if (Array.isArray(rag)) return rag
  if (rag.documents) return rag.documents
  return []
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
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
.debug-page {
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

.debug-content-wrapper {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.tab-header h3 {
  margin: 0;
  color: var(--accent-secondary);
}

.debug-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 48px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.02);
  border-radius: 12px;
}

.debug-section {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: rgba(233, 69, 96, 0.1);
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.section-header:hover {
  background: rgba(233, 69, 96, 0.15);
}

.section-header span:first-child {
  font-weight: 600;
}

.toggle-icon {
  font-size: 12px;
  color: var(--text-secondary);
}

.section-content {
  padding: 16px;
  border-top: 1px solid var(--border-color);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item label {
  font-size: 12px;
  color: var(--text-secondary);
}

.info-item span {
  font-size: 14px;
  font-family: 'JetBrains Mono', monospace;
}

.info-item.highlight span {
  color: var(--accent-secondary);
  font-weight: 600;
}

.json-viewer {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  padding: 12px;
  max-height: 300px;
  overflow: auto;
}

.json-viewer pre {
  margin: 0;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-primary);
}

.rag-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rag-item {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
}

.rag-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.rag-index {
  font-weight: 600;
  color: var(--accent-secondary);
}

.rag-score {
  font-size: 12px;
  color: var(--text-secondary);
}

.rag-content {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
  max-height: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.empty-section {
  color: var(--text-secondary);
  font-style: italic;
}

.tts-text {
  margin-top: 12px;
}

.tts-text label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.tts-text pre {
  margin: 0;
  background: rgba(0, 0, 0, 0.2);
  padding: 10px;
  border-radius: 6px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.debug-footer {
  text-align: center;
  padding: 12px;
  color: var(--text-secondary);
  font-size: 12px;
}
</style>
