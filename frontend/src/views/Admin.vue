<template>
  <div class="admin-page">
    <div class="page-header">
      <h1 class="title"><img src="/emojis/三月七_盯.png" class="emoji-icon-lg" /> 后台管理</h1>
      <p>管理员专用页面</p>
    </div>

    <div class="admin-tabs">
      <button
        :class="['tab-btn', { active: activeTab === 'conversations' }]"
        @click="activeTab = 'conversations'"
      >
        <img src="/emojis/三月七_悄悄话.png" class="emoji-icon" /> 对话管理
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'users' }]"
        @click="activeTab = 'users'"
      >
        <img src="/emojis/三月七_暗中观察.png" class="emoji-icon" /> 用户管理
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'characters' }]"
        @click="activeTab = 'characters'"
      >
        <img src="/emojis/三月七_盯.png" class="emoji-icon" /> 角色管理
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'settings' }]"
        @click="activeTab = 'settings'"
      >
        <img src="/emojis/三月七_买买买.png" class="emoji-icon" /> 系统设置
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'debug' }]"
        @click="activeTab = 'debug'"
      >
        <img src="/emojis/三月七_吃糖.png" class="emoji-icon" /> 调试面板
      </button>
    </div>

    <div class="admin-content">
      <div v-if="activeTab === 'conversations'" class="conversations-tab">
        <div class="tab-header">
          <div class="filter-group">
            <label>角色筛选:</label>
            <select v-model="roleFilter" class="input-field" @change="loadConversations">
              <option value="all">全部</option>
              <option value="user">用户</option>
              <option value="admin">管理员</option>
            </select>
          </div>
          <div class="filter-group">
            <label>评分筛选:</label>
            <select v-model="ratingFilter" class="input-field">
              <option value="all">全部</option>
              <option value="rated">已评分</option>
              <option value="unrated">待评分</option>
            </select>
          </div>
          <div class="search-group">
            <input
              v-model="searchKeyword"
              type="text"
              class="input-field search-input"
              placeholder="搜索对话内容..."
              @keydown.enter="searchConversations"
            />
            <button class="btn btn-secondary" @click="searchConversations" :disabled="searching">
              {{ searching ? '搜索中...' : '🔍 搜索' }}
            </button>
            <button v-if="searchKeyword" class="btn btn-secondary" @click="clearSearch">
              清除
            </button>
          </div>
          <button class="btn btn-secondary" @click="loadConversations(); loadSuggestionLoopStats()">
            🔄 刷新
          </button>
        </div>

        <div class="stats-cards">
          <div class="stat-card">
            <div class="stat-header">
              <img src="/emojis/三月七_biu.png" class="emoji-icon" />
              <span class="stat-title">自动生成建议</span>
            </div>
            <div class="stat-value">{{ suggestionLoopStats?.auto_generated ?? 0 }}</div>
            <div class="stat-desc">系统自动检测生成（全局）</div>
          </div>
          <div class="stat-card">
            <div class="stat-header">
              <img src="/emojis/三月七_吃糖.png" class="emoji-icon" />
              <span class="stat-title">待确认建议</span>
            </div>
            <div class="stat-value warning">{{ suggestionLoopStats?.auto_pending ?? 0 }}</div>
            <div class="stat-desc">等待人工确认入库</div>
          </div>
          <div class="stat-card">
            <div class="stat-header">
              <img src="/emojis/三月七_点赞.png" class="emoji-icon" />
              <span class="stat-title">已确认建议</span>
            </div>
            <div class="stat-value positive">{{ suggestionLoopStats?.auto_confirmed ?? 0 }}</div>
            <div class="stat-desc">确认后写入 RAG 知识库</div>
          </div>
          <div class="stat-card">
            <div class="stat-header">
              <img src="/emojis/三月七_暗中观察.png" class="emoji-icon" />
              <span class="stat-title">已驳回建议</span>
            </div>
            <div class="stat-value">{{ suggestionLoopStats?.auto_rejected ?? 0 }}</div>
            <div class="stat-desc">驳回后不写入 RAG</div>
          </div>
          <div class="stat-card">
            <div class="stat-header">
              <img src="/emojis/三月七_骄傲.png" class="emoji-icon" />
              <span class="stat-title">确认闭环率</span>
            </div>
            <div class="stat-value accent">{{ confirmRateText }}</div>
            <div class="stat-desc">已确认 / 已处理建议</div>
          </div>
          <div class="stat-card">
            <div class="stat-header">
              <img src="/emojis/三月七_开心.png" class="emoji-icon" />
              <span class="stat-title">RAG 累计更新数</span>
            </div>
            <div class="stat-value positive">{{ suggestionLoopStats?.rag_updated_total ?? 0 }}</div>
            <div class="stat-desc">反馈确认后累计写入 RAG</div>
          </div>
        </div>
        <div class="loop-pipeline-hint">
          建议闭环：对话 → 自动检测生成建议 → 人工确认写入 RAG / 驳回拦截 → 画像优化
        </div>

        <div v-if="searchResults.length > 0" class="search-results-info">
          <span>找到 {{ searchResults.length }} 条匹配的对话</span>
        </div>

        <div class="data-table">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>用户</th>
                <th>权限</th>
                <th>角色</th>
                <th>用户输入</th>
                <th>机器人回复</th>
                <th>评分</th>
                <th>时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="conv in displayedConversations" :key="conv.id">
                <td>{{ conv.id }}</td>
                <td>{{ conv.username }}</td>
                <td>{{ conv.role === 'admin' ? '管理员' : '用户' }}</td>
                <td>{{ conv.character }}</td>
                <td class="text-cell">{{ conv.user_input }}</td>
                <td class="text-cell">{{ conv.bot_reply }}</td>
                <td>{{ conv.rating ? conv.rating + '⭐' : '-' }}</td>
                <td>{{ formatTime(conv.timestamp) }}</td>
                <td>
                  <div class="action-buttons">
                    <button class="btn btn-secondary btn-sm" @click="showExportMenu(conv.id)">
                      📥 导出
                    </button>
                    <div v-if="activeExportConv === conv.id" class="export-menu">
                      <button class="export-option" @click="exportConversation(conv.id, 'markdown')">
                        Markdown
                      </button>
                      <button class="export-option" @click="exportConversation(conv.id, 'json')">
                        JSON
                      </button>
                    </div>
                    <button class="btn btn-danger btn-sm" @click="deleteConversation(conv.id)">
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="activeTab === 'users'" class="users-tab">
        <div class="tab-header">
          <button class="btn btn-secondary" @click="loadUsers">
            🔄 刷新
          </button>
        </div>

        <div class="data-table">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>用户名</th>
                <th>角色</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td>{{ user.id }}</td>
                <td>{{ user.username }}</td>
                <td>
                  <select 
                    :value="user.role" 
                    class="input-field role-select"
                    @change="updateUserRole(user.id, $event.target.value)"
                    :disabled="user.username === 'admin'"
                  >
                    <option value="user">用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </td>
                <td>{{ formatTime(user.created_at) }}</td>
                <td>
                  <button 
                    class="btn btn-danger btn-sm" 
                    @click="deleteUser(user.id)"
                    :disabled="user.role === 'admin'"
                  >
                    删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="activeTab === 'characters'" class="characters-tab">
        <div class="tab-header">
          <button class="btn btn-secondary" @click="loadUserCharacters">
            🔄 刷新
          </button>
        </div>

        <div class="data-table">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>来源</th>
                <th>用户</th>
                <th>角色名称</th>
                <th>LLM模型</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="char in userCharacters" :key="char.id + '-' + char.source">
                <td>{{ char.id }}</td>
                <td>
                  <span 
                    class="source-tag" 
                    :class="char.source === 'admin' ? 'source-admin' : 'source-user'"
                  >
                    {{ char.source === 'admin' ? '管理员角色' : '用户创建' }}
                  </span>
                </td>
                <td>{{ char.username || '-' }}</td>
                <td>{{ char.name }}</td>
                <td>{{ char.llm_model || '-' }}</td>
                <td>{{ char.created_at ? formatTime(char.created_at) : '-' }}</td>
                <td>
                  <div class="action-buttons">
                    <button 
                      v-if="char.source === 'admin'" 
                      class="btn btn-primary btn-sm" 
                      @click="showImportDialog(char)"
                    >
                      📥 导入
                    </button>
                    <button 
                      v-if="char.source === 'admin'" 
                      class="btn btn-secondary btn-sm" 
                      @click="viewCharacter(char)"
                    >
                    查看
                    </button>
                    <button 
                      v-if="char.source === 'user_created'" 
                      class="btn btn-secondary btn-sm" 
                      @click="editCharacter(char)"
                    >
                      编辑
                    </button>
                    <button 
                      v-if="char.source === 'user_created'" 
                      class="btn btn-danger btn-sm" 
                      @click="deleteCharacter(char.id)"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="importingCharacter" class="edit-modal">
          <div class="modal-overlay" @click="closeImportDialog"></div>
          <div class="modal-content">
            <h3>📥 导入全局角色</h3>
            <div class="import-info">
              <p class="import-name">角色名称: <strong>{{ importingCharacter.name }}</strong></p>
              <p class="import-desc">将全局角色导入到数据库，导入后可以自定义编辑。</p>
              <div class="import-details">
                <div class="detail-item">
                  <span class="detail-label">LLM 模型:</span>
                  <span class="detail-value">{{ importingCharacter.llm_model || '-' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">RAG 启用:</span>
                  <span class="detail-value">{{ importingCharacter.rag_enabled ? '是' : '否' }}</span>
                </div>
              </div>
            </div>
            <div class="modal-actions">
              <button class="btn btn-secondary" @click="closeImportDialog">取消</button>
              <button class="btn btn-primary" @click="confirmImport" :disabled="importing">
                {{ importing ? '导入中...' : '确认导入' }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="viewingCharacter" class="edit-modal">
          <div class="modal-overlay" @click="closeViewModal"></div>
          <div class="modal-content">
            <h3>👁️ 查看角色详情</h3>
            <div class="form-group">
              <label>角色名称</label>
              <input v-model="viewingCharacter.character_data.name" class="input-field" disabled />
            </div>
            <div class="form-group">
              <label>LLM 模型</label>
              <input v-model="viewingCharacter.character_data.llm_model" class="input-field" disabled />
            </div>
            <div class="form-group">
              <label>系统提示词</label>
              <textarea v-model="viewingCharacter.character_data.system_prompt" class="input-field" rows="4" disabled></textarea>
            </div>
            <div class="form-group">
              <label>Temperature</label>
              <input :value="viewingCharacter.character_data.temperature" type="number" step="0.1" class="input-field" disabled />
            </div>
            <div class="form-group">
              <label>Top P</label>
              <input :value="viewingCharacter.character_data.top_p" type="number" step="0.1" class="input-field" disabled />
            </div>
            <div class="form-group">
              <label>RAG Collection</label>
              <input v-model="viewingCharacter.character_data.rag_collection" class="input-field" disabled />
            </div>
            <div class="form-group">
              <label>
                <input v-model="viewingCharacter.character_data.rag_enabled" type="checkbox" disabled />
                RAG 启用
              </label>
            </div>
            <div class="modal-actions">
              <button class="btn btn-secondary" @click="closeViewModal">关闭</button>
              <button class="btn btn-primary" @click="importFromView">
                📥 导入此角色
              </button>
            </div>
          </div>
        </div>

        <div v-if="editingCharacter" class="edit-modal">
          <div class="modal-overlay" @click="closeEditModal"></div>
          <div class="modal-content">
            <h3>编辑角色</h3>
            <div class="form-group">
              <label>角色名称</label>
              <input v-model="editingCharacter.character_data.name" class="input-field" />
            </div>
            <div class="form-group">
              <label>LLM 模型</label>
              <input v-model="editingCharacter.character_data.llm_model" class="input-field" />
            </div>
            <div class="form-group">
              <label>系统提示词</label>
              <textarea v-model="editingCharacter.character_data.system_prompt" class="input-field" rows="4"></textarea>
            </div>
            <div class="form-group">
              <label>Temperature</label>
              <div class="slider-with-value">
                <input v-model.number="editingCharacter.character_data.temperature" type="range" step="0.1" min="0" max="2" class="slider-input" />
                <span class="slider-value">{{ editingCharacter.character_data.temperature }}</span>
              </div>
            </div>
            <div class="form-group">
              <label>Top P</label>
              <div class="slider-with-value">
                <input v-model.number="editingCharacter.character_data.top_p" type="range" step="0.1" min="0" max="1" class="slider-input" />
                <span class="slider-value">{{ editingCharacter.character_data.top_p }}</span>
              </div>
            </div>
            <div class="form-group">
              <label>RAG Collection</label>
              <input v-model="editingCharacter.character_data.rag_collection" class="input-field" />
            </div>
            <div class="form-group">
              <label>
                <input v-model="editingCharacter.character_data.rag_enabled" type="checkbox" />
                RAG 启用
              </label>
            </div>

            <div class="modal-actions">
              <button class="btn btn-secondary" @click="closeEditModal">取消</button>
              <button class="btn btn-primary" @click="saveCharacter">保存</button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'settings'" class="settings-tab">
        <div class="tab-header">
          <h3>⚙️ 系统设置</h3>
          <button class="btn btn-secondary" @click="loadSettings">
            🔄 刷新
          </button>
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

      <div v-if="activeTab === 'debug'" class="debug-tab">
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
              <div v-if="!hasRagResults() && !getRagConfig().enabled" class="empty-section">RAG 未启用</div>
              <div v-else-if="!hasRagResults() && getRagConfig().enabled" class="empty-section">RAG 已启用但无检索结果 (状态: {{ getRagConfig().status || 'unknown' }})</div>
              <div v-else class="rag-list">
                <div class="info-grid" style="margin-bottom: 12px;">
                  <div class="info-item">
                    <label>RAG 启用:</label>
                    <span>{{ getRagConfig().enabled ? '✅ 是' : '❌ 否' }}</span>
                  </div>
                  <div class="info-item">
                    <label>检索状态:</label>
                    <span :class="['rag-status', getRagConfig().status]">{{ getRagStatusLabel(getRagConfig().status) }}</span>
                  </div>
                  <div class="info-item">
                    <label>Top K:</label>
                    <span>{{ getRagConfig().top_k || '-' }}</span>
                  </div>
                  <div class="info-item">
                    <label>距离阈值:</label>
                    <span>{{ getRagConfig().distance_threshold || '-' }}</span>
                  </div>
                  <div class="info-item" style="grid-column: 1 / -1;">
                    <label>检索查询:</label>
                    <span class="rag-query-text">{{ getRagConfig().query || '-' }}</span>
                  </div>
                  <div class="info-item">
                    <label>检索文档数:</label>
                    <span>{{ getRagDocuments().length }}</span>
                  </div>
                </div>
                <div v-for="(doc, index) in getRagDocuments()" :key="index" class="rag-item">
                  <div class="rag-header">
                    <span class="rag-index">文档 {{ index + 1 }}</span>
                    <span class="rag-score">距离: {{ doc.distance ?? '-' }}</span>
                    <span class="rag-score" v-if="doc.similarity != null">相似度: {{ doc.similarity }}</span>
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../utils/api'

const activeTab = ref('conversations')
const conversations = ref([])
const users = ref([])
const userCharacters = ref([])
const roleFilter = ref('all')
const ratingFilter = ref('all')
const debugInfo = ref(null)
const editingCharacter = ref(null)
const viewingCharacter = ref(null)
const importingCharacter = ref(null)
const importing = ref(false)
const activeExportConv = ref(null)
const expandedSections = ref({
  llm: true,
  tokens: true,
  prompt: false,
  rag: true,
  tts: true,
  timing: true,
})

const searchKeyword = ref('')
const searchResults = ref([])
const searching = ref(false)

// 建议闭环统计（数据源: /api/rag/suggestions/stats?scope=all，管理员全局口径）
// 五项指标: 自动生成 / 待确认 / 已确认 / 已驳回 / 确认闭环率
const suggestionLoopStats = ref(null)

const confirmRateText = computed(() => {
  const rate = suggestionLoopStats.value?.confirm_rate
  if (rate === null || rate === undefined) return '—'
  return `${(rate * 100).toFixed(1)}%`
})

// 表格展示的对话：搜索结果优先，并按评分筛选（已评分/待评分）本地过滤
const displayedConversations = computed(() => {
  const list = searchResults.value.length > 0 ? searchResults.value : conversations.value
  if (ratingFilter.value === 'rated') {
    return list.filter(c => c.rating != null && c.rating !== undefined)
  }
  if (ratingFilter.value === 'unrated') {
    return list.filter(c => c.rating == null || c.rating === undefined)
  }
  return list
})

const settings = ref({
  securityFilterEnabled: true,
  proxyEnabled: false,
  proxyUrl: '',
  verboseLogging: false
})
const settingsMessage = ref('')
const settingsMessageType = ref('success')

onMounted(() => {
  loadConversations()
  loadSuggestionLoopStats()
  loadUsers()
  loadUserCharacters()
  loadDebugInfo()
  loadSettings()
})

async function loadSuggestionLoopStats() {
  try {
    const response = await api.get('/rag/suggestions/stats', { scope: 'all' })
    if (response.success) {
      suggestionLoopStats.value = response.stats || null
    }
  } catch (e) {
    console.error('Failed to load suggestion loop stats:', e)
  }
}

async function loadConversations() {
  try {
    const response = await api.get('/admin/conversations', { role: roleFilter.value })
    if (response.success) {
      conversations.value = response.conversations
    }
  } catch (e) {
    console.error('Failed to load conversations:', e)
  }
}

async function searchConversations() {
  if (!searchKeyword.value.trim()) {
    searchResults.value = []
    return
  }
  
  searching.value = true
  searchResults.value = []
  
  try {
    const response = await api.get('/admin/conversations/search', {
      keyword: searchKeyword.value.trim()
    })
    
    if (response.success) {
      searchResults.value = response.results || []
    }
  } catch (e) {
    console.error('Failed to search conversations:', e)
  } finally {
    searching.value = false
  }
}

function clearSearch() {
  searchKeyword.value = ''
  searchResults.value = []
}

async function loadUsers() {
  try {
    const response = await api.get('/admin/users')
    if (response.success) {
      users.value = response.users
    }
  } catch (e) {
    console.error('Failed to load users:', e)
  }
}

async function loadUserCharacters() {
  try {
    const response = await api.get('/admin/user-characters')
    if (response.success) {
      userCharacters.value = response.characters
    }
  } catch (e) {
    console.error('Failed to load user characters:', e)
  }
}

async function loadSettings() {
  try {
    const response = await api.get('/admin/settings')
    if (response.success && response.settings) {
      settings.value = { ...settings.value, ...response.settings }
    }
  } catch (e) {
    console.error('Failed to load settings:', e)
  }
}

async function saveSettings() {
  try {
    await api.put('/admin/settings', settings.value)
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

function viewCharacter(char) {
  viewingCharacter.value = {
    id: char.id,
    name: char.name,
    character_data: { ...char.character_data }
  }
}

function closeViewModal() {
  viewingCharacter.value = null
}

function showImportDialog(char) {
  importingCharacter.value = char
}

function closeImportDialog() {
  importingCharacter.value = null
}

async function confirmImport() {
  if (!importingCharacter.value) return
  
  importing.value = true
  try {
    const response = await api.post(`/admin/characters/import/${importingCharacter.value.id}`)
    if (response.success) {
      alert(`✅ ${response.message}`)
      closeImportDialog()
      await loadUserCharacters()
    }
  } catch (e) {
    alert('导入失败: ' + (e.detail || '未知错误'))
  } finally {
    importing.value = false
  }
}

async function importFromView() {
  if (!viewingCharacter.value) return
  
  const char = viewingCharacter.value
  closeViewModal()
  showImportDialog(userCharacters.value.find(c => c.id === char.id))
}

function closeEditModal() {
  editingCharacter.value = null
}

async function saveCharacter() {
  if (!editingCharacter.value) return

  const charData = editingCharacter.value.character_data
  
  // Build complete character config including TTS and emotions
  const fullConfig = {
    name: charData.name || '',
    llm_model: charData.llm_model || '',
    system_prompt: charData.system_prompt || '',
    temperature: charData.temperature ?? 1.0,
    top_p: charData.top_p ?? 0.9,
    rag_collection: charData.rag_collection || '',
    rag_enabled: charData.rag_enabled || false,
    tts_config: {
      gpt_weight: charData.tts_gpt_weight || '',
      sovits_weight: charData.tts_sovits_weight || '',
      ref_audio_path: charData.tts_ref_audio_path || '',
      ref_audio_text: charData.tts_ref_audio_text || '',
      port: charData.tts_port || 9880,
      version: charData.tts_version || 'v2ProPlus',
    },
    emotions: charData.emotions || {},
    iteration_apis: charData.iteration_apis || [],
  }

  try {
    await api.put(`/admin/user-characters/${editingCharacter.value.id}`, {
      character_data: fullConfig
    })
    await loadUserCharacters()
    closeEditModal()
  } catch (e) {
    alert('保存失败: ' + (e.detail || '未知错误'))
  }
}

function editCharacter(char) {
  const cd = { ...char.character_data }
  
  cd.emotions = cd.emotions || {}
  cd.iteration_apis = cd.iteration_apis || []
  const defaultEmotions = ['neutral', 'happy', 'confused', 'sad', 'angry', 'excited']
  defaultEmotions.forEach(em => {
    if (!cd.emotions[em]) {
      cd.emotions[em] = { ref_audio_path: '', ref_text: '' }
    }
  })

  // Flatten TTS config for easy editing
  if (cd.tts_config) {
    cd.tts_gpt_weight = cd.tts_config.gpt_weight || ''
    cd.tts_sovits_weight = cd.tts_config.sovits_weight || ''
    cd.tts_ref_audio_path = cd.tts_config.ref_audio_path || ''
    cd.tts_ref_audio_text = cd.tts_config.ref_audio_text || ''
    cd.tts_port = cd.tts_config.port || 9880
    cd.tts_version = cd.tts_config.version || 'v2ProPlus'
  }

  editingCharacter.value = {
    id: char.id,
    character_data: cd
  }
}

async function deleteCharacter(id) {
  if (!confirm('确定要删除这个角色吗？')) return

  try {
    await api.delete(`/admin/user-characters/${id}`)
    await loadUserCharacters()
  } catch (e) {
    alert('删除失败: ' + (e.detail || '未知错误'))
  }
}

async function loadDebugInfo() {
  try {
    const response = await api.get('/admin/debug-info')
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

function getRagConfig() {
  if (!debugInfo.value) return {}
  const rag = debugInfo.value.rag
  if (rag && !Array.isArray(rag) && typeof rag === 'object') {
    return {
      enabled: rag.enabled ?? false,
      status: rag.status ?? 'unknown',
      top_k: rag.top_k ?? 0,
      distance_threshold: rag.distance_threshold ?? 0,
      query: rag.query ?? '',
    }
  }
  return { enabled: false, status: 'unknown' }
}

function getRagStatusLabel(status) {
  const labels = {
    ok: '✅ 正常检索',
    partial: '⚠️ 部分结果',
    no_results: '❌ 无结果',
    unknown: '❓ 未知',
  }
  return labels[status] || status || '❓ 未知'
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

async function deleteConversation(id) {
  if (!confirm('确定要删除这条对话记录吗？')) return
  
  try {
    await api.delete(`/admin/conversations/${id}`)
    await loadConversations()
  } catch (e) {
    alert('删除失败: ' + (e.detail || '未知错误'))
  }
}

async function updateUserRole(userId, newRole) {
  try {
    await api.put(`/admin/users/${userId}/role?role=${newRole}`)
    await loadUsers()
  } catch (e) {
    alert('更新失败: ' + (e.detail || '未知错误'))
    await loadUsers()
  }
}

function showExportMenu(convId) {
  activeExportConv.value = activeExportConv.value === convId ? null : convId
}

async function exportConversation(convId, format) {
  activeExportConv.value = null

  try {
    const response = await api.get(`/admin/conversations/${convId}/export?format=${format}`)

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
    alert('导出失败')
  }
}

async function deleteUser(userId) {
  if (!confirm('确定要删除这个用户吗？')) return
  
  try {
    await api.delete(`/admin/users/${userId}`)
    await loadUsers()
  } catch (e) {
    alert('删除失败: ' + (e.detail || '未知错误'))
  }
}

function formatTime(timestamp) {
  if (!timestamp) return '-'
  return timestamp.replace('T', ' ').substring(0, 19)
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
.admin-page {
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

.admin-tabs {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.tab-btn {
  padding: 14px 24px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  color: var(--text-primary);
  font-size: 15px;
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.tab-btn.active {
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.3) 0%, rgba(255, 107, 157, 0.2) 100%);
  border-color: var(--accent-primary);
  color: var(--accent-secondary);
}

.admin-content {
  flex: 1;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 20px;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
}

.admin-content::-webkit-scrollbar {
  width: 8px;
}

.admin-content::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

.admin-content::-webkit-scrollbar-thumb {
  background: rgba(233, 69, 96, 0.4);
  border-radius: 4px;
}

.admin-content::-webkit-scrollbar-thumb:hover {
  background: rgba(233, 69, 96, 0.6);
}

.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-group label {
  color: var(--text-secondary);
}

.filter-group .input-field {
  width: 150px;
}

.search-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  max-width: 400px;
}

.search-input {
  flex: 1;
}

.search-results-info {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(233, 69, 96, 0.1);
  border-radius: 8px;
  font-size: 14px;
  color: var(--accent-secondary);
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-title {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-primary);
}

.stat-value.accent {
  color: var(--accent-secondary);
}

.stat-value.positive {
  color: #4caf50;
}

.stat-value.warning {
  color: #ff9800;
}

.stat-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.loop-pipeline-hint {
  margin-bottom: 16px;
  padding: 8px 12px;
  background: rgba(66, 133, 244, 0.08);
  border: 1px solid rgba(66, 133, 244, 0.2);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.data-table {
  flex: 1;
  overflow: auto;
}

.data-table::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.data-table::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 3px;
}

.data-table::-webkit-scrollbar-thumb {
  background: rgba(233, 69, 96, 0.3);
  border-radius: 3px;
}

.data-table::-webkit-scrollbar-thumb:hover {
  background: rgba(233, 69, 96, 0.5);
}

.data-table table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th {
  background: rgba(233, 69, 96, 0.2);
  color: var(--accent-secondary);
  padding: 14px 12px;
  text-align: left;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 10;
  backdrop-filter: blur(8px);
}

.data-table td {
  padding: 12px;
  border-bottom: 1px solid var(--border-color);
}

.data-table tr:hover td {
  background: rgba(233, 69, 96, 0.1);
}

.text-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-sm {
  padding: 8px 16px;
  font-size: 13px;
}

.role-select {
  padding: 6px 12px;
  font-size: 13px;
}

.conversations-tab, .users-tab {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.conversations-tab::-webkit-scrollbar,
.users-tab::-webkit-scrollbar {
  width: 6px;
}

.conversations-tab::-webkit-scrollbar-track,
.users-tab::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 3px;
}

.conversations-tab::-webkit-scrollbar-thumb,
.users-tab::-webkit-scrollbar-thumb {
  background: rgba(233, 69, 96, 0.3);
  border-radius: 3px;
}

.settings-tab {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.settings-content {
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

.debug-tab {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.debug-tab::-webkit-scrollbar {
  width: 6px;
}

.debug-tab::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 3px;
}

.debug-tab::-webkit-scrollbar-thumb {
  background: rgba(233, 69, 96, 0.3);
  border-radius: 3px;
}

.debug-tab .tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.debug-tab .tab-header h3 {
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

.section-divider {
  font-size: 16px;
  font-weight: 600;
  color: var(--accent-secondary);
  margin: 20px 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

.section-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 12px;
}

.btn-small {
  padding: 6px 12px;
  font-size: 12px;
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

.rag-status {
  font-weight: 600;
}

.rag-status.ok {
  color: #4caf50;
}

.rag-status.partial {
  color: #ff9800;
}

.rag-status.no_results {
  color: #f44336;
}

.rag-query-text {
  font-family: monospace;
  background: rgba(0, 0, 0, 0.3);
  padding: 2px 8px;
  border-radius: 4px;
  word-break: break-all;
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

.characters-tab {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.characters-tab::-webkit-scrollbar {
  width: 6px;
}

.characters-tab::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 3px;
}

.characters-tab::-webkit-scrollbar-thumb {
  background: rgba(233, 69, 96, 0.3);
  border-radius: 3px;
}

.edit-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  justify-content: center;
  align-items: center;
}

.modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
}

.modal-content {
  position: relative;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 24px;
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin: 0 0 20px 0;
  color: var(--accent-secondary);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  color: var(--text-secondary);
  font-size: 14px;
}

.form-group textarea {
  resize: vertical;
  min-height: 80px;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
}

.export-menu {
  position: absolute;
  top: 100%;
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
  min-width: 100px;
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
  white-space: nowrap;
}

.export-option:hover {
  background: rgba(233, 69, 96, 0.2);
}

.source-tag {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.source-tag.source-admin {
  background: rgba(66, 133, 244, 0.2);
  color: #4285f4;
  border: 1px solid rgba(66, 133, 244, 0.3);
}

.source-tag.source-user {
  background: rgba(52, 168, 83, 0.2);
  color: #34a853;
  border: 1px solid rgba(52, 168, 83, 0.3);
}

.import-info {
  margin-bottom: 20px;
}

.import-name {
  font-size: 16px;
  margin-bottom: 8px;
}

.import-desc {
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 16px;
}

.import-details {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
}

.detail-label {
  color: var(--text-secondary);
  font-size: 14px;
}

.detail-value {
  font-size: 14px;
  font-family: 'JetBrains Mono', monospace;
}

.input-field:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-group label input[type="checkbox"]:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
</style>
