@echo off
chcp 65001 >nul
echo ========================================
echo   三月七语音对话系统启动脚本
echo ========================================
echo.

echo [1/2] 启动 FastAPI 后端...
start "FastAPI Backend" cmd /k "cd /d %~dp0 && python -m api.main"
timeout /t 3 /nobreak >nul

echo [2/2] 启动 Vue 前端...
start "Vue Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo   服务已启动！
echo   后端 API: http://127.0.0.1:8000
echo   API 文档: http://127.0.0.1:8000/docs
echo   前端页面: http://localhost:5173
echo ========================================
echo.
echo 请在前端页面打开后访问系统
echo.
pause
