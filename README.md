# 三月七语音对话系统 (March 7th Voice Chat System)

基于本地大语言模型(LLM)和语音合成(TTS)的角色扮演对话系统，用户可以与"三月七"（星穹列车角色）进行语音对话。

## 目录

- [核心特性](#核心特性)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [Docker 部署](#docker-部署)
- [API 文档](#api-文档)
- [核心功能详解](#核心功能详解)
- [配置说明](#配置说明)
- [项目结构](#项目结构)

---

## 核心特性

- **角色扮演对话** - 与"三月七"角色进行沉浸式对话，保持角色人格一致性
- **语音输入识别** - 支持语音输入，实现语音对话体验
- **语音合成输出** - 使用 GPT-SoVITS 进行高质量语音合成
- **RAG 知识库增强** - 基于 ChromaDB 的检索增强生成，提供角色背景知识
- **流式响应 (SSE)** - 支持 Server-Sent Events 实时流式输出
- **多用户系统** - 完整的用户认证和权限管理
- **用户偏好学习** - 基于时间衰减算法的个性化偏好分析
- **用户画像摘要** - 自动生成用户画像摘要，实现个性化对话
- **配置热重载** - 支持角色配置文件热重载，无需重启服务
- **管理员后台** - 用户管理、对话记录管理等功能

---

## 技术栈

### 后端
| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.12 | 主要开发语言 |
| FastAPI | 0.109+ | Web API 框架 |
| Uvicorn | 0.27+ | ASGI 服务器 |
| PyJWT | 2.8+ | JWT 认证 |
| PyMySQL | 1.1+ | MySQL 数据库连接 |
| bcrypt | 4.0+ | 密码加密 |
| jieba | 0.42+ | 中文分词 |
| tiktoken | - | Token 计数 |
| sentence-transformers | - | 文本嵌入 |
| chromadb | - | 向量数据库 |
| ollama | - | LLM 推理接口 |

### 前端
| 技术 | 版本 | 用途 |
|------|------|------|
| Vue.js | 3.4+ | 前端框架 |
| Vite | 5.0+ | 构建工具 |
| Pinia | 2.1+ | 状态管理 |
| Vue Router | 4.2+ | 路由管理 |
| Axios | 1.6+ | HTTP 客户端 |
| marked | 11.0+ | Markdown 解析 |

### 数据库 & AI 服务
| 服务 | 用途 |
|------|------|
| MySQL 8.0 | 主数据库 |
| Ollama | 本地 LLM 推理 |
| deepseek-r1:8b | 默认 LLM 模型 |
| GPT-SoVITS v2ProPlus | 语音合成 |

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- MySQL 8.0+
- Ollama (已安装 deepseek-r1:8b 模型)
- GPT-SoVITS 服务 (可选，用于语音合成)

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd march_7th
```

2. **安装 Python 依赖**
```bash
pip install -r requirements.txt
```

3. **配置数据库**

创建 MySQL 数据库：
```sql
CREATE DATABASE march7th_chat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

创建 `personal_config.py` 文件：
```python
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "march7th_chat",
    "charset": "utf8mb4",
}

OLLAMA_CONFIG = {
    "default_model": "deepseek-r1:8b",
    "alternative_models": ["qwen3.5:9b"],
    "base_url": "http://localhost:11434",
}

ADMIN_CONFIG = {
    "default_username": "admin",
    "default_password": "admin123",
}

JWT_CONFIG = {
    "secret": "your_jwt_secret_key",
    "expire_hours": 24,
}
```

4. **安装前端依赖**
```bash
cd frontend
npm install
```

5. **启动服务**

方式一：使用启动脚本
```bash
python run.py
```

方式二：分别启动
```bash
# 后端
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# 前端 (新终端)
cd frontend
npm run dev
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:5173 |
| 后端 API | http://127.0.0.1:8000 |
| API 文档 | http://127.0.0.1:8000/docs |
| Ollama API | http://127.0.0.1:11434 |
| TTS API | http://127.0.0.1:9880 |

---

## Docker 部署

项目支持完整的 Docker 容器化部署。

### 使用 Docker Compose

1. **创建环境变量文件**

创建 `.env` 文件：
```env
MYSQL_ROOT_PASSWORD=march7th_root_password
MYSQL_USER=march7th
MYSQL_PASSWORD=march7th_password
JWT_SECRET=march7th_jwt_secret_key_2024_very_secure
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
OLLAMA_HOST=host.docker.internal:11434
GPT_SOVITS_DIR=/app/gpt-sovits
```

2. **启动核心服务**
```bash
docker-compose up -d
```

这将启动：
- MySQL 数据库
- 后端 API 服务
- 前端 Web 服务

3. **启动可选服务**

启动 Ollama 容器：
```bash
docker-compose --profile ollama up -d ollama
```

启动 GPT-SoVITS 容器：
```bash
docker-compose --profile tts up -d gpt-sovits
```

### 服务配置

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 80 | Nginx 前端服务 |
| backend | 8000 | FastAPI 后端服务 |
| mysql | 3306 | MySQL 数据库 |
| ollama | 11434 | LLM 推理服务 (可选) |
| gpt-sovits | 9880 | TTS 服务 (可选) |

### 健康检查

所有服务都配置了健康检查：
- MySQL: 使用 `mysqladmin ping`
- Backend: 使用 `curl` 检查根路径
- Frontend: 依赖 backend 健康状态

---

## API 文档

### 认证接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/auth/register` | 用户注册 |
| GET | `/api/auth/me` | 获取当前用户信息 |

### 对话接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/chat` | 全流程对话（LLM + TTS） |
| POST | `/api/chat/stream` | **流式对话 (SSE)** |
| POST | `/api/chat/rating` | 提交评分 |
| GET | `/api/chat/history` | 获取对话历史 |
| POST | `/api/chat/clear` | 清除对话历史 |

### LLM 测试接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/llm/chat` | LLM 独立测试 |
| POST | `/api/llm/clear` | 清除 LLM 历史 |

### TTS 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/tts` | 文本转语音 |
| GET | `/api/tts/config` | 获取 TTS 配置 |

### 用户画像接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/profile` | 获取用户画像 |
| POST | `/api/profile/regenerate` | 重新生成画像摘要 |

### 角色接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/characters` | 获取角色列表 |
| GET | `/api/characters/{id}` | 获取角色详情 |
| POST | `/api/characters` | 创建/更新角色 |
| DELETE | `/api/characters/{id}` | 删除角色 |

### 配置管理接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/config/reload` | **手动重载配置** |
| GET | `/api/config/status` | 获取配置状态 |

### 管理员接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/admin/users` | 获取用户列表 |
| GET | `/api/admin/conversations` | 获取所有对话 |
| DELETE | `/api/admin/conversations/{id}` | 删除对话 |
| PUT | `/api/admin/users/{id}/role` | 更新用户角色 |
| DELETE | `/api/admin/users/{id}` | 删除用户 |

### 系统接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/system/status` | 获取系统状态 |

---

## 核心功能详解

### 流式响应 (SSE)

系统支持 Server-Sent Events (SSE) 流式响应，实现实时文本输出和语音合成。

#### 端点
```
POST /api/chat/stream
```

#### 请求体
```json
{
  "message": "你好",
  "character_id": "march7th",
  "model": "deepseek-r1:8b",
  "temperature": 1.0,
  "top_p": 0.9
}
```

#### 事件类型

| 事件 | 数据格式 | 说明 |
|------|----------|------|
| `text` | `{"content": "..."}` | 文本片段 |
| `audio` | `{"audio": "base64...", "text": "..."}` | 语音片段 |
| `done` | `{"conversation_id": 123}` | 完成事件 |
| `error` | `{"error": "..."}` | 错误事件 |

#### 前端示例
```javascript
const eventSource = new EventSource('/api/chat/stream', {
  method: 'POST',
  body: JSON.stringify({ message: '你好' })
});

eventSource.addEventListener('text', (e) => {
  const data = JSON.parse(e.data);
  console.log('Text:', data.content);
});

eventSource.addEventListener('audio', (e) => {
  const data = JSON.parse(e.data);
  const audio = new Audio(`data:audio/wav;base64,${data.audio}`);
  audio.play();
});

eventSource.addEventListener('done', (e) => {
  console.log('Conversation ID:', JSON.parse(e.data).conversation_id);
  eventSource.close();
});
```

### 用户偏好算法 (时间衰减)

系统使用**指数时间衰减算法**来计算用户偏好的有效权重，使近期偏好具有更高影响力。

#### 算法公式

```
有效权重 = 原始计数 × e^(-衰减率 × 天数)
```

#### 参数配置
```python
PREFERENCE_DECAY_RATE = 0.1  # 衰减率，值越大衰减越快
```

#### 算法特点

1. **时间敏感性** - 近期交互的偏好权重更高
2. **平滑衰减** - 使用指数函数，权重平滑下降
3. **可配置** - 可通过 `PREFERENCE_DECAY_RATE` 调整衰减速度

#### 示例

假设用户对"摄影"话题的偏好：
- 3天前提及 5 次：有效权重 = 5 × e^(-0.1 × 3) ≈ 3.70
- 10天前提及 5 次：有效权重 = 5 × e^(-0.1 × 10) ≈ 1.84
- 30天前提及 5 次：有效权重 = 5 × e^(-0.1 × 30) ≈ 0.25

#### 代码实现
```python
def calculate_decayed_weight(count: int, days_ago: float, decay_rate: float = 0.1) -> float:
    return count * math.exp(-decay_rate * days_ago)
```

### 用户画像摘要

系统自动生成用户画像摘要，用于个性化对话体验。

#### 功能特点

1. **自动触发** - 当对话 Token 数超过阈值时自动重新生成
2. **多维度分析** - 包含兴趣爱好、交流风格、情感倾向等
3. **偏好整合** - 结合用户偏好关键词进行分析
4. **上下文注入** - 生成的摘要自动注入到对话上下文

#### 配置参数
```python
PROFILE_SUMMARY_TOKEN_THRESHOLD = 10000  # Token 阈值
PROFILE_SUMMARY_MAX_TOKENS = 500         # 摘要最大长度
```

#### API 使用

获取画像：
```bash
GET /api/profile
```

手动重新生成：
```bash
POST /api/profile/regenerate
```

#### 画像摘要示例
```
兴趣爱好：用户喜欢讨论摄影、旅行和美食话题，对科技产品也有一定兴趣。
交流风格：用户倾向于简洁直接的沟通方式，喜欢使用表情符号。
情感倾向：用户情感表达积极正面，经常分享开心的事情。
其他特征：用户是游戏爱好者，对星穹铁道有深入了解。
```

### 配置热重载

系统支持角色配置文件的热重载，无需重启服务即可更新配置。

#### 功能特点

1. **自动监控** - 后台线程定期检查配置文件变更
2. **即时生效** - 检测到变更后自动重新加载
3. **回调机制** - 支持注册重载回调函数
4. **状态查询** - 可通过 API 查询配置状态

#### 配置参数
```python
CONFIG_AUTO_RELOAD = True      # 启用自动重载
CONFIG_CHECK_INTERVAL = 30     # 检查间隔（秒）
```

#### API 使用

手动触发重载：
```bash
POST /api/config/reload
```

响应：
```json
{
  "success": true,
  "reloaded": true,
  "message": "配置已重新加载",
  "timestamp": "2026-04-06T12:00:00"
}
```

查询配置状态：
```bash
GET /api/config/status
```

响应：
```json
{
  "success": true,
  "status": {
    "config_path": "/app/config/characters.json",
    "exists": true,
    "last_modified": 1712345678.123,
    "auto_reload": true,
    "watcher_active": true,
    "character_count": 3,
    "check_interval": 30
  }
}
```

### RAG 知识库

#### 混合检索 (BM25 + 向量)

系统使用 BM25 和向量检索的混合搜索策略，通过 RRF (Reciprocal Rank Fusion) 算法融合结果。

#### RRF 融合算法
```
RRF_score(d) = Σ 1/(k + rank(d))
# k = 60 (默认参数)
```

#### 特点
- BM25: 基于词频的精确匹配
- 向量检索: 语义相似度匹配
- RRF 融合: 综合两种检索结果

---

## 配置说明

### 全局配置 (config.py)

```python
# LLM 配置
LLM_MODEL = "deepseek-r1:8b"
LLM_MAX_TOKENS = 1024

# TTS 配置
TTS_PORT = 9880
TTS_VERSION = "v2ProPlus"

# 用户偏好配置
PREFERENCE_DECAY_RATE = 0.1

# 画像摘要配置
PROFILE_SUMMARY_TOKEN_THRESHOLD = 10000
PROFILE_SUMMARY_MAX_TOKENS = 500

# 配置热重载
CONFIG_AUTO_RELOAD = True
CONFIG_CHECK_INTERVAL = 30
```

### 角色配置 (config/characters.json)

```json
{
  "characters": [
    {
      "id": "march7th",
      "name": "三月七",
      "avatar_path": "",
      "llm_config": {
        "model": "deepseek-r1:8b",
        "system_prompt": "...",
        "temperature": 1.0,
        "top_p": 0.9
      },
      "tts_config": {
        "gpt_weight": "GPT_weights_v2ProPlus/march7th-e15.ckpt",
        "sovits_weight": "SoVITS_weights_v2ProPlus/march7th_e8_s5040.pth",
        "ref_audio_path": "output/ref_audio.wav",
        "ref_audio_text": "参考音频文本"
      },
      "rag_config": {
        "collection_name": "march7th_knowledge",
        "enabled": true,
        "top_k": 3
      }
    }
  ]
}
```

---

## 项目结构

```
march_7th/
├── api/                    # FastAPI 后端
│   ├── __init__.py
│   └── main.py            # API 主文件
├── frontend/              # Vue 前端
│   ├── src/
│   │   ├── views/        # 页面组件
│   │   ├── stores/       # Pinia 状态
│   │   ├── router/       # 路由配置
│   │   ├── utils/        # 工具函数
│   │   └── styles/       # 样式文件
│   ├── package.json
│   └── vite.config.js
├── config/               # 配置文件
│   └── characters.json   # 角色配置
├── rag_db/              # RAG 向量数据库
├── persona_db/          # Persona 向量数据库
├── tests/               # 测试文件
├── init-db/             # 数据库初始化脚本
├── logs/                # 日志目录
├── personal_config.py   # 个人配置
├── database.py          # 数据库管理
├── inference.py         # LLM 推理模块
├── tts_service.py       # TTS 服务模块
├── voice_chat.py        # 语音对话控制器
├── character_config.py  # 角色配置管理
├── user_preference.py   # 用户偏好分析
├── profile_summary.py   # 用户画像摘要
├── persona_manager.py   # Persona 管理
├── logger.py            # 日志模块
├── config.py            # 全局配置
├── run.py               # 启动脚本
├── Dockerfile           # Docker 镜像配置
├── docker-compose.yml   # Docker Compose 配置
└── requirements.txt     # Python 依赖
```

---

## 许可证

MIT License

---

**文档维护者**: AI Assistant  
**最后更新**: 2026-04-06
