@echo off
chcp 65001 >nul
title 七音盒系统启动器

echo.
echo ╔════════════════════════════════════════╗
echo ║      七音盒 (Music7ox) - 启动器        ║
echo ╚════════════════════════════════════════╝
echo.

set "PROJECT_ROOT=%~dp0"

:: 注意：^&^& 是对 & 的转义，使得命令能正确赋值
set BACKEND_CMD=cd /d "%PROJECT_ROOT%" ^&^& python -m api.main
set FRONTEND_CMD=cd /d "%PROJECT_ROOT%frontend" ^&^& npm run dev
set PET_CMD=cd /d "%PROJECT_ROOT%desktop_pet" ^&^& npm start

echo 请选择要启动的服务:
echo.
echo   [1] 仅后端 (FastAPI)
echo   [2] 仅前端 (Vue)
echo   [3] 仅桌宠 (Electron)
echo   [4] 后端 + 前端
echo   [5] 全部 (后端 + 前端 + 桌宠)
echo   [6] 仅桌宠
echo.
echo   [0] 退出
echo.

set /p choice="请输入选项 (默认5): "
if "%choice%"=="" set choice=5

if "%choice%"=="0" (
    echo 已取消
    exit /b 0
)

echo.
echo 正在启动服务...
echo.

if "%choice%"=="1" goto start_backend
if "%choice%"=="2" goto start_frontend
if "%choice%"=="3" goto start_pet
if "%choice%"=="4" goto start_backend_frontend
if "%choice%"=="5" goto start_all
if "%choice%"=="6" goto start_pet_only

echo 无效选项，启动全部服务...
goto start_all

:start_backend
echo [启动] 后端服务...
start "FastAPI Backend" cmd /k "%BACKEND_CMD%"
goto show_info

:start_frontend
echo [启动] 前端服务...
start "Vue Frontend" cmd /k "%FRONTEND_CMD%"
goto show_info

:start_pet
echo [启动] 桌宠服务...
start "Desktop Pet" cmd /k "%PET_CMD%"
goto show_info

:start_backend_frontend
echo [启动] 后端服务...
start "FastAPI Backend" cmd /k "%BACKEND_CMD%"
timeout /t 3 /nobreak >nul
echo [启动] 前端服务...
start "Vue Frontend" cmd /k "%FRONTEND_CMD%"
goto show_info

:start_all
echo [启动] 后端服务...
start "FastAPI Backend" cmd /k "%BACKEND_CMD%"
timeout /t 3 /nobreak >nul
echo [启动] 前端服务...
start "Vue Frontend" cmd /k "%FRONTEND_CMD%"
timeout /t 2 /nobreak >nul
echo [启动] 桌宠服务...
start "Desktop Pet" cmd /k "%PET_CMD%"
goto show_info

:start_pet_only
echo [启动] 桌宠服务...
start "Desktop Pet" cmd /k "%PET_CMD%"
goto show_info

:show_info
echo.
echo ╔════════════════════════════════════════╗
echo ║              服务地址                  ║
echo ╠════════════════════════════════════════╣
echo ║  后端 API:  http://127.0.0.1:8000      ║
echo ║  API 文档:  http://127.0.0.1:8000/docs ║
echo ║  前端页面:  http://localhost:5173      ║
echo ╚════════════════════════════════════════╝
echo.
echo 提示: 关闭此窗口不会影响已启动的服务
echo.
pause