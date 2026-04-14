#!/usr/bin/env python3
"""
下载 Sherpa-ONNX 中文流式语音识别模型
"""
import os
import shutil
import urllib.request
import tarfile
from pathlib import Path

def get_models_dir():
    """获取 models 目录路径（脚本所在目录）"""
    return Path(__file__).parent.resolve()

class DownloadProgress:
    def __init__(self):
        self.last_percent = -1
        self.downloaded = 0
        self.total = 0
    
    def __call__(self, count, block_size, total_size):
        self.downloaded = count * block_size
        self.total = total_size
        
        if total_size > 0:
            percent = int((self.downloaded / total_size) * 100)
            if percent != self.last_percent:
                self.last_percent = percent
                mb_downloaded = self.downloaded / 1024 / 1024
                mb_total = total_size / 1024 / 1024
                print(f"\r下载进度: {percent}% ({mb_downloaded:.1f}MB / {mb_total:.1f}MB)", end='', flush=True)
        else:
            mb_downloaded = self.downloaded / 1024 / 1024
            print(f"\r已下载: {mb_downloaded:.1f}MB", end='', flush=True)

def download_asr_model():
    """下载中英双语流式ASR模型"""
    models_dir = get_models_dir()
    asr_model_dir = models_dir / "asr_model"
    
    if asr_model_dir.exists():
        print(f"ASR模型目录已存在: {asr_model_dir}")
        return asr_model_dir
    
    print("正在下载中英双语流式ASR模型...")
    print("模型: sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20")
    
    github_url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2"
    
    mirrors = [
        ("ghproxy.com", f"https://ghproxy.com/{github_url}"),
        ("mirror.ghproxy.com", f"https://mirror.ghproxy.com/{github_url}"),
        ("gh-proxy.com", f"https://gh-proxy.com/{github_url}"),
        ("GitHub原始", github_url),
    ]
    
    tar_path = models_dir / "asr_model.tar.bz2"
    
    for mirror_name, model_url in mirrors:
        try:
            print(f"\n尝试从 {mirror_name} 下载...")
            print(f"URL: {model_url}")
            
            progress = DownloadProgress()
            urllib.request.urlretrieve(model_url, tar_path, progress)
            print("\n下载完成！")
            break
            
        except KeyboardInterrupt:
            print("\n用户取消下载")
            if tar_path.exists():
                tar_path.unlink()
            return None
        except Exception as e:
            print(f"\n从 {mirror_name} 下载失败: {e}")
            if tar_path.exists():
                tar_path.unlink()
            continue
    else:
        print("\n所有镜像都下载失败！")
        print("\n请手动下载模型:")
        print("方法1: 使用浏览器下载（推荐使用IDM等下载工具）")
        print(f"  {github_url}")
        print(f"  下载后放到: {tar_path}")
        print("\n方法2: 使用GitHub镜像站")
        print(f"  https://ghproxy.com/{github_url}")
        print("\n方法3: 使用命令行工具")
        print(f"  curl -L -o {tar_path} https://ghproxy.com/{github_url}")
        return None
    
    try:
        print("\n解压中...")
        with tarfile.open(tar_path, 'r:bz2') as tar:
            tar.extractall(models_dir)
        
        extracted_dir = models_dir / "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20"
        if extracted_dir.exists():
            extracted_dir.rename(asr_model_dir)
            print(f"模型已解压到: {asr_model_dir}")
        
        tar_path.unlink()
        print("清理临时文件完成")
        
        return asr_model_dir
        
    except Exception as e:
        print(f"解压失败: {e}")
        return None

def verify_asr_model():
    """验证ASR模型文件"""
    models_dir = get_models_dir()
    asr_model_dir = models_dir / "asr_model"
    
    required_files = [
        'encoder-epoch-99-avg-1.onnx',
        'decoder-epoch-99-avg-1.onnx', 
        'joiner-epoch-99-avg-1.onnx',
        'tokens.txt'
    ]
    
    print("\n验证ASR模型:")
    all_ok = True
    for fname in required_files:
        fpath = asr_model_dir / fname
        if fpath.exists():
            size = fpath.stat().st_size / 1024 / 1024
            print(f"  ✓ {fname} ({size:.1f} MB)")
        else:
            print(f"  ✗ {fname} (不存在)")
            all_ok = False
    
    return all_ok

if __name__ == "__main__":
    print("=" * 60)
    print("Sherpa-ONNX 中文流式语音识别模型下载工具")
    print("=" * 60)
    
    models_dir = get_models_dir()
    print(f"目标目录: {models_dir}\n")
    
    asr_model_dir = download_asr_model()
    if asr_model_dir:
        verify_asr_model()
        print("\n" + "=" * 60)
        print("ASR模型下载完成！")
        print("现在可以使用语音识别功能了")
        print("=" * 60)
