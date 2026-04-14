# 唤醒词检测安装指南

本功能使用 Sherpa-ONNX 实现本地唤醒词检测，支持自定义中文唤醒词。

## 安装步骤

### 1. 安装 Node.js 依赖

```bash
cd desktop_pet
npm install sherpa-onnx mic
```

### 2. 下载中文唤醒词模型

**方法 A: 使用 Python 脚本（推荐）**

```bash
cd desktop_pet/models
pip install modelscope
python download_model.py
```

**方法 B: 手动下载**

1. 从以下地址下载模型：
   - GitHub: https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01.tar.bz2
   - ModelScope（国内更快）: https://modelscope.cn/models/pkufool/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01

2. 解压后将以下文件重命名并放入 `models/` 目录：
   - `encoder-epoch-99-avg-1-chunk-16-left-64.onnx` → `encoder.onnx`
   - `decoder-epoch-99-avg-1-chunk-16-left-64.onnx` → `decoder.onnx`
   - `joiner-epoch-99-avg-1-chunk-16-left-64.onnx` → `joiner.onnx`
   - `tokens.txt` → `tokens.txt`

### 3. 配置唤醒词

编辑 `kws_config.json` 或 `models/keywords.txt`：

**keywords.txt 格式：**
```
s an1 y ve4 q i1 @三月七
```

**拼音格式说明：**
- 每个音节用空格分隔
- 声调用数字表示：1=阴平, 2=阳平, 3=上声, 4=去声, 5=轻声
- `@` 后面是显示名称

**常用唤醒词拼音：**
| 汉字 | 拼音 |
|------|------|
| 三月七 | s an1 y ve4 q i1 |
| 你好小七 | n i3 h ao3 x iao3 q i1 |
| 小三月 | x iao3 s an1 y ve4 |

### 4. 运行

```bash
cd desktop_pet
npm start
```

## 工作原理

```
桌宠启动 → 自动后台监听麦克风
    ↓
用户说"三月七" → 本地模型检测到唤醒词
    ↓
通知前端 → 桌宠表情变化 → 启动完整语音识别
    ↓
用户继续说话 → 语音转文字 → 发送到后端
    ↓
获得回复 → TTS播放 → 回到后台监听
```

## 隐私说明

- ✅ **完全本地处理**：唤醒词检测在本地进行，不上传音频
- ✅ **低功耗**：模型仅 3.3MB，CPU 占用极低
- ✅ **无网络依赖**：唤醒词检测不需要网络连接

## 故障排除

### 问题：找不到 sherpa-onnx 模块
```bash
cd desktop_pet
npm install sherpa-onnx
```

### 问题：找不到 mic 模块
```bash
cd desktop_pet
npm install mic
```

### 问题：模型文件不存在
确保 `models/` 目录下有以下文件：
- encoder.onnx
- decoder.onnx
- joiner.onnx
- tokens.txt

### 问题：macOS 麦克风权限
在 macOS 上需要在"系统偏好设置 > 安全性与隐私 > 隐私 > 麦克风"中允许 Electron 访问麦克风。
