# Sherpa-ONNX 中文唤醒词模型

## 模型信息
- 模型名称: sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01
- 模型大小: 3.3MB
- 训练数据: WenetSpeech (10000小时中文数据)
- 建模单元: 拼音（声母 + 韵母）

## 下载模型

### 方法1: 从 GitHub 下载
```bash
# Windows PowerShell
cd e:\world\python\march_7th\desktop_pet\models
Invoke-WebRequest -Uri "https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01.tar.bz2" -OutFile "model.tar.bz2"
tar -xf model.tar.bz2
mv sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01/* .
rm -r sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01 model.tar.bz2
```

### 方法2: 从 ModelScope 下载（国内推荐）
```bash
pip install modelscope
python download_model.py
```

## 模型文件结构
```
models/
├── encoder.onnx      # 编码器模型
├── decoder.onnx      # 解码器模型
├── joiner.onnx       # 连接器模型
├── tokens.txt        # 拼音Token映射表
└── keywords.txt      # 唤醒词配置文件
```

## 唤醒词配置
在 keywords.txt 中配置唤醒词，格式：
```
s an1 y ve4 q i1 @三月七
```

拼音格式说明：
- 每个音节用空格分隔
- 声调用数字表示（1=阴平, 2=阳平, 3=上声, 4=去声, 5=轻声）
- @后面是显示的关键词名称
