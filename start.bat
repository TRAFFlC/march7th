@echo off
chcp 65001 >nul

echo ========================================
echo    Music7ox - Starting
echo ========================================
echo.

echo [1/3] Starting backend...
start "Music7ox-Backend" cmd /k "cd /d %~dp0 && python -m api.main"
timeout /t 3 /nobreak >nul

echo [2/3] Starting frontend...
start "Music7ox-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
timeout /t 2 /nobreak >nul

echo [3/3] Starting desktop pet...
start "Music7ox-DesktopPet" cmd /k "cd /d %~dp0desktop_pet && npm start"

echo.
echo ========================================
echo    Service URLs
echo ========================================
echo   Backend API:  http://127.0.0.1:8000
echo   API Docs:     http://127.0.0.1:8000/docs
echo   Frontend:     http://localhost:5173
echo ========================================
echo.
echo All services started!
echo.
echo Press any key to exit this window...
pause >nul
