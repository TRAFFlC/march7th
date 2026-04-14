#!/usr/bin/env python3
"""
下载 Sherpa-ONNX 中文唤醒词模型并整理到标准位置
"""
import os
import shutil
from pathlib import Path

def get_models_dir():
    """获取 models 目录路径（脚本所在目录）"""
    return Path(__file__).parent.resolve()

def download_from_modelscope():
    """从 ModelScope 下载模型（国内推荐）"""
    try:
        from modelscope import snapshot_download
        print("正在从 ModelScope 下载模型...")
        model_dir = snapshot_download(
            'pkufool/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01',
            cache_dir=str(get_models_dir() / '.cache')
        )
        print(f"模型下载完成: {model_dir}")
        return Path(model_dir)
    except ImportError:
        print("未安装 modelscope，请运行: pip install modelscope")
        return None
    except Exception as e:
        print(f"下载失败: {e}")
        return None

def organize_model_files(model_dir):
    """将模型文件复制到标准位置"""
    models_dir = get_models_dir()

    # 文件映射：目标文件名 -> 源文件匹配模式
    file_mappings = {
        'encoder.onnx': 'encoder-epoch-12-avg-2-chunk-16-left-64.onnx',
        'decoder.onnx': 'decoder-epoch-12-avg-2-chunk-16-left-64.onnx',
        'joiner.onnx': 'joiner-epoch-12-avg-2-chunk-16-left-64.onnx',
        'tokens.txt': 'tokens.txt',
    }

    for target_name, pattern in file_mappings.items():
        src = model_dir / pattern
        dst = models_dir / target_name

        if src.exists():
            shutil.copy2(src, dst)
            print(f"已复制: {dst.name} ({src.stat().st_size / 1024:.1f} KB)")
        else:
            print(f"警告: 源文件不存在 {src}")

    # 清理子目录
    for item in model_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item)

    print("\n模型文件已整理到标准位置！")
    print(f"目录: {models_dir}")

def verify_installation():
    """验证安装"""
    models_dir = get_models_dir()
    required_files = ['encoder.onnx', 'decoder.onnx', 'joiner.onnx', 'tokens.txt']

    print("\n验证安装:")
    all_ok = True
    for fname in required_files:
        fpath = models_dir / fname
        if fpath.exists():
            size = fpath.stat().st_size / 1024
            print(f"  ✓ {fname} ({size:.1f} KB)")
        else:
            print(f"  ✗ {fname} (不存在)")
            all_ok = False

    return all_ok

if __name__ == "__main__":
    print("=" * 50)
    print("Sherpa-ONNX 中文唤醒词模型下载工具")
    print("=" * 50)

    models_dir = get_models_dir()
    print(f"目标目录: {models_dir}\n")

    # 检查是否已有模型文件
    encoder_exists = (models_dir / 'encoder.onnx').exists()

    if encoder_exists:
        print("模型文件已存在，跳过下载。")
        verify_installation()
    else:
        model_dir = download_from_modelscope()
        if model_dir:
            organize_model_files(model_dir)
            verify_installation()
