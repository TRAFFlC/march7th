@echo off
chcp 65001 >nul
title 七音盒 Music7ox

echo ========================================
echo    七音盒 Music7ox - 一键启动
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 启动后端服务...
start "Music7ox-Backend" cmd /k "python -m api.main"
timeout /t 3 /nobreak >nul

echo [2/3] 启动前端服务...
start "Music7ox-Frontend" cmd /k "cd frontend && npm run dev"
timeout /t 2 /nobreak >nul

echo [3/3] 启动桌宠...
start "Music7ox-DesktopPet" cmd /k "cd desktop_pet && npm start"

echo.
echo ========================================
echo    服务地址
echo ========================================
echo   后端 API:  http://127.0.0.1:8000
echo   API 文档:  http://127.0.0.1:8000/docs
echo   前端界面:  http://localhost:5173
echo ========================================
echo.
echo 所有服务已启动！
echo.
echo 提示：如需关闭服务，关闭对应的命令行窗口即可
pause
