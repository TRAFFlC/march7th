# 桌宠模型文件夹

本目录包含桌宠运行所需的模型文件。

## 文件夹说明

| 文件夹 | 说明 | 状态 |
|--------|------|------|
| `asr_model/` | ASR语音识别模型 | 需从网盘下载 |

## ASR语音识别模型下载

**百度网盘链接**: https://pan.baidu.com/s/1AZMToyyzKdWhumaSeNWPcQ
**提取码**: 3yue

### 包含文件

下载 `asr_model` 文件夹后，将其移动到 `desktop_pet/models/` 目录。

最终目录结构应为：
```
desktop_pet/models/
├── asr_model/           # 从网盘下载后放入
│   ├── encoder-epoch-99-avg-1.onnx
│   ├── encoder-epoch-99-avg-1.int8.onnx
│   ├── decoder-epoch-99-avg-1.onnx
│   ├── decoder-epoch-99-avg-1.int8.onnx
│   ├── joiner-epoch-99-avg-1.onnx
│   ├── joiner-epoch-99-avg-1.int8.onnx
│   ├── bpe.model
│   ├── bpe.vocab
│   └── tokens.txt
└── README.md  (本文件)
```
