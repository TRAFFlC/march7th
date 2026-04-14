"""
显存释放验证脚本
测试 ollama.stop() 后显存能否完全释放

运行方式: python test_memory_release.py
"""
import ollama
import torch
import time
import subprocess

MODEL_NAME = "deepseek-r1:8b"

def check_gpu_memory():
    """检查当前GPU显存占用(GB)"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        return allocated, reserved
    return 0, 0

def check_nvidia_smi():
    """通过nvidia-smi检查显存(MB)"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True
        )
        return float(result.stdout.strip().split('\n')[0])
    except Exception as e:
        print(f"nvidia-smi查询失败: {e}")
        return None

def main():
    print("=" * 60)
    print("显存释放验证测试")
    print("=" * 60)

    print("\n[1] 初始状态检查")
    alloc_before, res_before = check_gpu_memory()
    smi_before = check_nvidia_smi()
    print(f"  torch.cuda.memory_allocated: {alloc_before:.3f} GB")
    print(f"  torch.cuda.memory_reserved:   {res_before:.3f} GB")
    print(f"  nvidia-smi:                  {smi_before:.0f} MB ({smi_before/1024:.2f} GB)")

    print("\n[2] 启动Ollama并加载模型")
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": "你好"}],
            options={"num_predict": 50}
        )
        print(f"  模型响应: {response['message']['content'][:50]}...")
    except Exception as e:
        print(f"  错误: {e}")
        print("  请确保ollama服务正在运行: ollama serve")
        return

    time.sleep(1)
    print("\n[3] 模型加载后状态")
    alloc_loaded, res_loaded = check_gpu_memory()
    smi_loaded = check_nvidia_smi()
    print(f"  torch.cuda.memory_allocated: {alloc_loaded:.3f} GB")
    print(f"  torch.cuda.memory_reserved:   {res_loaded:.3f} GB")
    print(f"  nvidia-smi:                  {smi_loaded:.0f} MB ({smi_loaded/1024:.2f} GB)")

    print("\n[4] 调用 ollama stop 释放模型")
    try:
        result = subprocess.run(
            ["ollama", "stop", MODEL_NAME],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"  ollama stop 执行成功: {result.stdout.strip()}")
        else:
            print(f"  ollama stop 警告: {result.stderr.strip()}")
    except Exception as e:
        print(f"  ollama stop 失败: {e}")
        print("  尝试使用taskkill强制终止...")
        try:
            subprocess.run(["taskkill", "/F", "/IM", "ollama.exe"],
                         capture_output=True, timeout=10)
            print("  taskkill 执行成功")
        except Exception as e2:
            print(f"  taskkill 也失败: {e2}")

    print("  等待2秒...")
    time.sleep(2)

    print("\n[5] 释放后状态")
    alloc_after, res_after = check_gpu_memory()
    smi_after = check_nvidia_smi()
    print(f"  torch.cuda.memory_allocated: {alloc_after:.3f} GB")
    print(f"  torch.cuda.memory_reserved:   {res_after:.3f} GB")
    print(f"  nvidia-smi:                  {smi_after:.0f} MB ({smi_after/1024:.2f} GB)")

    print("\n" + "=" * 60)
    print("结果汇总")
    print("=" * 60)
    print(f"模型加载前: {smi_before:.0f} MB")
    print(f"模型加载后: {smi_loaded:.0f} MB")
    print(f"stop释放后: {smi_after:.0f} MB")

    memory_freed = smi_loaded - smi_after
    print(f"\n释放显存: {memory_freed:.0f} MB ({memory_freed/1024:.2f} GB)")

    if smi_after < 500:
        print("\n✅ 显存释放成功! (< 500MB)")
        print("   可以安全进行TTS加载")
    elif smi_after < 2000:
        print("\n⚠️ 显存释放不完全，但剩余较少")
        print("   建议检查是否有其他进程占用")
    else:
        print("\n❌ 显存释放失败!")
        print("   建议使用 taskkill 强制终止ollama进程")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
