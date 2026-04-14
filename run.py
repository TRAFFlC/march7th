"""
启动脚本 - 同时启动 FastAPI 后端和 Vue 前端
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def main():
    project_dir = Path(__file__).parent
    frontend_dir = project_dir / "frontend"
    
    print("\n" + "=" * 50)
    print("  三月七语音对话系统启动中...")
    print("=" * 50 + "\n")
    
    print("[1/2] 启动 FastAPI 后端...")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(project_dir),
    )
    
    time.sleep(2)
    
    print("[2/2] 启动 Vue 前端...")
    
    if not (frontend_dir / "node_modules").exists():
        print("检测到首次运行，正在安装前端依赖...")
        subprocess.run(["npm", "install"], cwd=str(frontend_dir), shell=True)
    
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(frontend_dir),
        shell=True,
    )
    
    print("\n" + "=" * 50)
    print("  服务已启动！")
    print("  后端 API: http://127.0.0.1:8000")
    print("  API 文档: http://127.0.0.1:8000/docs")
    print("  前端页面: http://localhost:5173")
    print("=" * 50 + "\n")
    
    print("按 Ctrl+C 停止所有服务...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        backend_process.terminate()
        frontend_process.terminate()
        print("服务已停止")

if __name__ == "__main__":
    main()
