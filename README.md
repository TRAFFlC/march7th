# 七音盒 Music7ox

> 以《崩坏·星穹铁道》中的「三月七」为角色示例的角色语音对话系统
> 基于本地大语言模型（也兼容OpenAI API格式的外部API）与语音合成（GPT-SoVITS v2ProPlus）的角色语音对话系统。支持自定义角色语音克隆、RAG 知识库增强、情感识别（？）与桌宠语音交互。

你们也可以按照GPTSoVITS教程自行配置新角色，遇到问题可以联系本人，联系方式在README最后

## 特性

- **角色语音对话** -- 自定义角色配置，每个角色拥有独立的系统提示词、TTS 模型与 RAG 知识库
- **本地 LLM 推理** -- 通过 Ollama 运行本地大语言模型，数据不出本机
- **GPT-SoVITS 语音合成** -- 高质量角色语音克隆，只需 1-2 分钟参考音频即可训练
- **RAG 知识库增强** -- ChromaDB 向量检索 + BM25 混合检索，让角色更了解背景设定
- **情感识别与动态表情** -- 自动识别对话情感，驱动角色表情变化
- **桌面桌宠** -- Electron 桌面悬浮角色，支持语音唤醒与即时对话

---

## 环境要求

| 依赖       | 版本      | 说明          |
| ---------- | --------- | ------------- |
| Python     | 3.10+     | 推荐 3.12     |
| Node.js    | 18+       | 前端与桌宠    |
| MySQL      | 8.0+      | 主数据库      |
| Ollama     | 最新版    | 本地 LLM 推理 |
| GPT-SoVITS | v2ProPlus | 语音合成服务  |

---

## 完整部署指南

### 第一步：安装 MySQL

1. 下载并安装 [MySQL 8.0](https://dev.mysql.com/downloads/mysql/)
2. 创建数据库：

```sql
CREATE DATABASE march7th_chat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 第二步：安装 Ollama 并下载模型

1. 下载安装 [Ollama](https://ollama.ai)
2. 拉取模型（推荐 deepseek-r1:8b）：

```bash
ollama pull deepseek-r1:8b
```

其他模型也可选：

```bash
ollama pull qwen3.5:9b      # 通义千问
ollama pull llama3.1:8b     # Llama 3.1
```

### 第三步：安装 GPT-SoVITS

这是语音合成的核心组件，需要单独部署。

#### 3.1 下载 GPT-SoVITS

从百度网盘或直链下载整合包（推荐），或从 GitHub 克隆：

```bash
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
```

**重要**：将 GPT-SoVITS 文件夹放在与本项目（march7th）**平级**的目录下。例如：

```
D:\projects\
├── march7th\          # 本项目
└── GPT-SoVITS\        # GPT-SoVITS
```

#### 3.2 安装依赖

打开 GPT-SoVITS 目录，运行 `go-webui.bat`（Windows）启动 WebUI，系统会自动安装依赖。

#### 3.3 角色语音模型

**三月七的语音模型权重需要单独下载**（文件较大，无法上传至GitHub）：

| 文件 | 说明 | 大小 |
|------|------|------|
| march7th-e15.ckpt | GPT模型权重 | ~148MB |
| march7th_e8_s5040.pth | SoVITS模型权重 | ~165MB |

**下载地址**：
- 百度网盘链接：https://pan.baidu.com/s/1AZMToyyzKdWhumaSeNWPcQ
- 提取码：3yue

下载后将两个文件放置到 `resources/tts/models/` 目录。

如需训练自定义角色模型，请参考 [GPT-SoVITS 整合包教程](https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e/xyyqrfwiu3e2bgyk)。

#### 3.4 参考音频

**本项目已内置三月七的参考音频文件**，位于 `resources/tts/ref_audio/` 目录，无需额外准备。

如需自定义角色，同样参考上述教程准备参考音频。

### 第四步：克隆项目并安装依赖

```bash
git clone https://github.com/你的用户名/march7th.git
cd march7th

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && npm install && cd ..

# 安装桌宠依赖
cd desktop_pet && npm install && cd ..
```

### 第五步：下载大模型文件

本项目包含的部分模型文件较大（超过GitHub 100MB限制），需要单独下载。

**所有大模型文件都在同一个百度网盘链接中**：
- 百度网盘链接：https://pan.baidu.com/s/1AZMToyyzKdWhumaSeNWPcQ
- 提取码：3yue

#### TTS语音模型

| 文件 | 说明 | 大小 |
|------|------|------|
| march7th-e15.ckpt | GPT模型权重 | ~148MB |
| march7th_e8_s5040.pth | SoVITS模型权重 | ~165MB |

下载后将两个文件放置到 `resources/tts/models/` 目录。

#### ASR语音识别模型（桌宠用）

| 文件夹 | 说明 | 大小 |
|--------|------|------|
| asr_model/ | 包含6个.onnx模型文件 | ~530MB |

下载后移动整个 `asr_model` 文件夹到 `desktop_pet/models/` 目录。

### 第六步：配置环境变量

```bash
# 复制示例配置
cp .env.example .env
```

编辑 `.env` 文件，填写以下必要配置：

```env
# 数据库配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的MySQL密码
MYSQL_DATABASE=march7th_chat

# JWT 密钥（随便填一个复杂字符串）
JWT_SECRET=your_random_secret_string_here

# LLM 模型（确保已通过 ollama pull 下载）
LLM_MODEL=deepseek-r1:8b

# GPT-SoVITS 安装目录（与本项目平级）
GPT_SOVITS_DIR=../GPT-SoVITS
```

### 第七步：启动服务

直接双击 `start.bat` 文件即可启动所有服务。

**方式二：PowerShell 启动**

```powershell
.\start_all.ps1
```

**方式三：分别启动**

```bash
# 终端 1：后端
python -m api.main

# 终端 2：前端
cd frontend && npm run dev

# 终端 3：桌宠（可选）
cd desktop_pet && npm start
```

### 第八步：访问系统

| 服务     | 地址                       |
| -------- | -------------------------- |
| 前端页面 | http://localhost:5173      |
| 后端 API | http://127.0.0.1:8000      |
| API 文档 | http://127.0.0.1:8000/docs |

系统会自动登录，无需手动注册。

---

## 项目结构

```
march7th/
├── api/                    # FastAPI 后端
│   └── main.py
├── frontend/               # Vue.js 前端
│   └── src/
├── desktop_pet/            # Electron 桌面桌宠
│   ├── main.js
│   └── models/             # ASR/KWS 模型
├── config/                 # 配置文件
│   ├── characters.json     # 角色配置
│   └── prompts/            # 提示词模板
├── resources/              # 资源文件
│   ├── tts/                # TTS 模型与参考音频
│   │   ├── models/         # GPT/SoVITS 权重
│   │   └── ref_audio/      # 参考音频
│   └── rag/                # RAG 知识库文本
├── .env.example            # 环境变量示例
├── start_all.ps1           # 一键启动脚本
└── requirements.txt        # Python 依赖
```

---

## 技术栈

| 层级   | 技术                             |
| ------ | -------------------------------- |
| 前端   | Vue 3 + Vite + Pinia             |
| 后端   | Python + FastAPI                 |
| LLM    | Ollama                           |
| TTS    | GPT-SoVITS v2ProPlus             |
| RAG    | ChromaDB + sentence-transformers |
| 数据库 | MySQL 8.0                        |
| 桌宠   | Electron + sherpa-onnx           |

---

## 常见问题

遇到问题可以：

- 联系作者：QQ 3249878231 | B站 bili_48058474338 | 贴吧 彩虹天际线
- 或询问 AI（如 ChatGPT、Claude 等），提供错误日志可获得更准确的帮助

---

## 写在最后

- 本系统是基于我个人开发的一个完整系统而实现的单机重构。重构完之后并没有充分测试所有功能。遇到问题请见谅。
- 迫于时间、精力、成本，很多预想暂时未能实现。同时兼任开发者和用户、测试人员，也让我对需求的认识极为局限。
- 需求是第一要务，有任何需求、问题、建议都可以随时联系我，这将为系统开发提供最宝贵的支持。
