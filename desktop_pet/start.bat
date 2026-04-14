@echo off
chcp 65001 >nul
title 三月七桌宠启动器

echo ========================================
echo     三月七虚拟桌宠启动器
echo ========================================
echo.

cd /d "%~dp0"

if not exist "node_modules" (
    echo [INFO] 正在安装依赖...
    call npm install
    if errorlevel 1 (
        echo [ERROR] 依赖安装失败！
        pause
        exit /b 1
    )
)

echo [OK] 依赖检查完成
echo.
echo [INFO] 正在启动三月七桌宠...
echo [INFO] 确保后端服务已启动 (http://127.0.0.1:8000)
echo.
echo ========================================
echo.

npm start

if errorlevel 1 (
    echo.
    echo [ERROR] 启动失败！
    pause
)
