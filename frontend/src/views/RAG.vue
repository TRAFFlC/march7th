<template>
  <div class="rag-page">
    <div class="page-header">
      <h1 class="title"><img src="/emojis/三月七_暗中观察.png" class="emoji-icon-lg" /> RAG 知识库管理</h1>
      <p>管理角色知识库，上传文本构建 RAG</p>
    </div>

    <div v-if="loading" class="loading-state">
      <span class="loading-icon"><img src="/emojis/三月七_开心.png" class="emoji-icon-lg spin" /></span>
      <p>加载中...</p>
    </div>

    <div v-else class="rag-container">
      <div class="rag-status-section">
        <h3><img src="/emojis/三月七_盯.png" class="emoji-icon" /> 角色 RAG 状态</h3>
        <div class="status-grid">
          <div v-for="item in ragStatus" :key="item.character_id" class="status-card">
            <div class="status-header">
              <span class="character-name">{{ item.character_name }}</span>
              <span :class="['rag-badge', item.rag_enabled ? 'enabled' : 'disabled']">
                {{ item.rag_enabled ? 'RAG 启用' : 'RAG 禁用' }}
              </span>
            </div>
            <div class="status-details">
              <div class="status-row">
                <span class="status-label">集合名称</span>
                <span class="status-value">{{ item.collection_name || '未配置' }}</span>
              </div>
              <div class="status-row">
                <span class="status-label">文档数量</span>
                <span class="status-value">{{ item.document_count }}</span>
              </div>
              <div class="status-row">
                <span class="status-label">集合状态</span>
                <span :class="['status-value', item.has_collection ? 'exists' : 'missing']">
                  {{ item.has_collection ? '已创建' : '未创建' }}
                </span>
              </div>
            </div>
            <div class="status-actions" v-if="item.has_collection">
              <button class="btn btn-danger btn-sm" @click="confirmDelete(item)">
                🗑️ 删除集合
              </button>
            </div>
          </div>
        </div>
        <div v-if="ragStatus.length === 0" class="empty-state">
          <p>暂无角色信息</p>
        </div>
      </div>

      <div class="rag-build-section">
        <h3><img src="/emojis/三月七_加油.png" class="emoji-icon" /> 构建 RAG 知识库</h3>
        <p class="section-hint">上传 TXT 文件为角色生成 RAG 知识库</p>
        
        <div class="build-form">
          <div class="form-group">
            <label>选择角色</label>
            <select v-model="selectedCharacterId" class="input-field">
              <option value="">请选择角色</option>
              <option v-for="item in ragStatus" :key="item.character_id" :value="item.character_id">
                {{ item.character_name }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label>上传 TXT 文件（支持多选）</label>
            <div class="file-upload-area" @click="triggerFileInput" @dragover.prevent @drop.prevent="handleDrop">
              <input 
                ref="fileInputRef" 
                type="file" 
                accept=".txt" 
                multiple
                @change="handleFileSelect" 
                style="display: none" 
              />
              <div v-if="selectedFiles.length === 0" class="upload-placeholder">
                <span>📄 点击或拖拽 TXT 文件到此处（支持多选）</span>
              </div>
              <div v-else class="upload-selected">
                <div class="file-list">
                  <div v-for="(file, index) in selectedFiles" :key="index" class="file-item">
                    <span>📎 {{ file.name }}</span>
                    <button class="btn btn-secondary btn-sm" @click.stop="removeFile(index)">移除</button>
                  </div>
                </div>
                <button class="btn btn-secondary btn-sm clear-all-btn" @click.stop="clearFiles">清空全部</button>
              </div>
            </div>
          </div>

          <div class="form-group">
            <label>或直接输入文本内容</label>
            <textarea 
              v-model="textContent" 
              class="input-field" 
              placeholder="在此粘贴文本内容..."
              rows="6"
            ></textarea>
          </div>

          <button 
            class="btn btn-primary" 
            @click="buildRag" 
            :disabled="building || (selectedFiles.length === 0 && !textContent.trim()) || !selectedCharacterId"
          >
            {{ building ? '构建中...' : '🔨 构建 RAG' }}
          </button>

          <div v-if="buildResult" :class="['build-result', buildResult.success ? 'success' : 'error']">
            {{ buildResult.message }}
          </div>
        </div>
      </div>
    </div>

    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="showDeleteConfirm = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>确认删除</h3>
          <button class="modal-close" @click="showDeleteConfirm = false">&times;</button>
        </div>
        <div class="modal-body">
          <p>确定要删除角色「{{ deletingItem?.character_name }}」的 RAG 集合吗？此操作不可恢复。</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showDeleteConfirm = false">取消</button>
          <button class="btn btn-danger" @click="deleteRag" :disabled="deleting">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../utils/api'

const loading = ref(true)
const ragStatus = ref([])
const selectedCharacterId = ref('')
const selectedFiles = ref([])
const textContent = ref('')
const building = ref(false)
const buildResult = ref(null)
const fileInputRef = ref(null)
const showDeleteConfirm = ref(false)
const deletingItem = ref(null)
const deleting = ref(false)

async function fetchRagStatus() {
  loading.value = true
  try {
    const response = await api.get('/rag/status')
    if (response.success) {
      ragStatus.value = response.status
    }
  } catch (e) {
    console.error('Failed to fetch RAG status:', e)
  } finally {
    loading.value = false
  }
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function handleFileSelect(event) {
  const files = event.target.files
  if (files) {
    for (const file of files) {
      if (file.name.endsWith('.txt') && !selectedFiles.value.some(f => f.name === file.name)) {
        selectedFiles.value.push(file)
      }
    }
  }
}

function handleDrop(event) {
  const files = event.dataTransfer?.files
  if (files) {
    for (const file of files) {
      if (file.name.endsWith('.txt') && !selectedFiles.value.some(f => f.name === file.name)) {
        selectedFiles.value.push(file)
      }
    }
  }
}

function removeFile(index) {
  selectedFiles.value.splice(index, 1)
}

function clearFiles() {
  selectedFiles.value = []
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

async function buildRag() {
  if (!selectedCharacterId.value) return
  if (selectedFiles.value.length === 0 && !textContent.value.trim()) return

  building.value = true
  buildResult.value = null

  try {
    let content = textContent.value
    
    if (selectedFiles.value.length > 0) {
      const fileContents = []
      for (const file of selectedFiles.value) {
        const fileContent = await file.text()
        fileContents.push(`【${file.name}】\n${fileContent}`)
      }
      content = fileContents.join('\n\n---\n\n')
      if (textContent.value.trim()) {
        content = content + '\n\n---\n\n' + textContent.value
      }
    }

    const response = await api.post('/rag/build', {
      character_id: selectedCharacterId.value,
      text_content: content
    })

    buildResult.value = {
      success: response.success,
      message: response.success ? response.message : (response.message || '构建失败')
    }

    if (response.success) {
      await fetchRagStatus()
      selectedFiles.value = []
      textContent.value = ''
      if (fileInputRef.value) {
        fileInputRef.value.value = ''
      }
    }
  } catch (e) {
    buildResult.value = {
      success: false,
      message: e.detail || e.message || '构建失败'
    }
  } finally {
    building.value = false
  }
}

function confirmDelete(item) {
  deletingItem.value = item
  showDeleteConfirm.value = true
}

async function deleteRag() {
  if (!deletingItem.value) return
  deleting.value = true

  try {
    const response = await api.delete(`/rag/${deletingItem.value.collection_name}`)
    if (response.success) {
      showDeleteConfirm.value = false
      await fetchRagStatus()
    }
  } catch (e) {
    console.error('Failed to delete RAG:', e)
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  fetchRagStatus()
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
.rag-page {
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
.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}
.rag-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.rag-status-section,
.rag-build-section {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 24px;
}
.rag-status-section h3,
.rag-build-section h3 {
  color: var(--accent-secondary);
  margin-bottom: 16px;
}
.section-hint {
  color: var(--text-secondary);
  font-size: 14px;
  margin: 0 0 16px 0;
}
.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.status-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  transition: all 0.3s ease;
}
.status-card:hover {
  border-color: var(--accent-primary);
}
.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.character-name {
  font-weight: 600;
  font-size: 16px;
}
.rag-badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
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
.status-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}
.status-row {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}
.status-label {
  color: var(--text-secondary);
}
.status-value {
  color: var(--text-primary);
}
.status-value.exists {
  color: #81c784;
}
.status-value.missing {
  color: #ff9800;
}
.status-actions {
  display: flex;
  justify-content: flex-end;
}
.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
}
.build-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.form-group {
  margin-bottom: 0;
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
.file-upload-area {
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  color: var(--text-secondary);
}
.file-upload-area:hover {
  border-color: var(--accent-primary);
  background: rgba(233, 69, 96, 0.05);
}
.upload-placeholder {
  font-size: 14px;
}
.upload-selected {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: var(--accent-secondary);
}
.file-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}
.clear-all-btn {
  margin-top: 4px;
}
.build-result {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
}
.build-result.success {
  background: rgba(129, 199, 132, 0.2);
  color: #81c784;
}
.build-result.error {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}
.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
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
  max-width: 440px;
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
  margin: 0;
}
.modal-close {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 24px;
  cursor: pointer;
}
.modal-close:hover {
  color: var(--accent-primary);
}
.modal-body {
  padding: 24px;
}
.modal-body p {
  color: var(--text-secondary);
  margin: 0;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid var(--border-color);
}
</style>
