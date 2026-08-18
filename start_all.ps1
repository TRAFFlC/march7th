$Host.UI.RawUI.WindowTitle = "七音盒 Music7ox Launcher"
$ProjectRoot = "E:\world\python\march_7th"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   七音盒 (Music7ox) - Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[Debug] Project Root: $ProjectRoot" -ForegroundColor Yellow
Write-Host "[Debug] Backend Path: $ProjectRoot\api\main.py" -ForegroundColor Yellow
Write-Host "[Debug] Frontend Path: $ProjectRoot\frontend\package.json" -ForegroundColor Yellow
Write-Host "[Debug] Pet Path: $ProjectRoot\desktop_pet\package.json" -ForegroundColor Yellow
Write-Host ""

if (!(Test-Path $ProjectRoot)) {
    Write-Host "[ERROR] Project root not found: $ProjectRoot" -ForegroundColor Red
    exit 1
}

function Test-Port {
    param([int]$Port)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $connect = $tcp.BeginConnect("127.0.0.1", $Port, $null, $null)
        $wait = $connect.AsyncWaitHandle.WaitOne(500, $false)
        if ($wait) {
            try { $tcp.EndConnect($connect) } catch {}
            $tcp.Close()
            return $true
        }
        $tcp.Close()
        return $false
    } catch {
        return $false
    }
}

function Get-ServiceStatus {
    Write-Host "Service Status:" -ForegroundColor Yellow
    $backend = Test-Port -Port 8000
    $frontend = Test-Port -Port 5173

    Write-Host "  Backend (8000): " -NoNewline
    if ($backend) { Write-Host "Running" -ForegroundColor Green } else { Write-Host "Stopped" -ForegroundColor Red }

    Write-Host "  Frontend (5173): " -NoNewline
    if ($frontend) { Write-Host "Running" -ForegroundColor Green } else { Write-Host "Stopped" -ForegroundColor Red }
    Write-Host ""
}

function Start-Backend {
    Write-Host "[Start] Backend..." -ForegroundColor Green
    $backendPath = $ProjectRoot + "\api\main.py"
    Write-Host "[Debug] Checking: $backendPath" -ForegroundColor Gray
    Write-Host "[Debug] Exists: $(Test-Path $backendPath)" -ForegroundColor Gray

    $cmd = "cd /d " + $ProjectRoot + " && python -m api.main"
    Write-Host "[Debug] Command: $cmd" -ForegroundColor Gray

    Start-Process cmd.exe -ArgumentList "/k", $cmd -WindowStyle Normal
    Start-Sleep -Seconds 3
}

function Start-Frontend {
    Write-Host "[Start] Frontend..." -ForegroundColor Green
    $frontendPath = $ProjectRoot + "\frontend\package.json"
    Write-Host "[Debug] Checking: $frontendPath" -ForegroundColor Gray
    Write-Host "[Debug] Exists: $(Test-Path $frontendPath)" -ForegroundColor Gray

    $cmd = "cd /d " + $ProjectRoot + "\frontend && npm run dev"
    Write-Host "[Debug] Command: $cmd" -ForegroundColor Gray

    Start-Process cmd.exe -ArgumentList "/k", $cmd -WindowStyle Normal
    Start-Sleep -Seconds 2
}

function Start-Pet {
    Write-Host "[Start] Desktop Pet..." -ForegroundColor Green
    $petPath = $ProjectRoot + "\desktop_pet\package.json"
    Write-Host "[Debug] Checking: $petPath" -ForegroundColor Gray
    Write-Host "[Debug] Exists: $(Test-Path $petPath)" -ForegroundColor Gray

    $cmd = "cd /d " + $ProjectRoot + "\desktop_pet && npm start"
    Write-Host "[Debug] Command: $cmd" -ForegroundColor Gray

    Start-Process cmd.exe -ArgumentList "/k", $cmd -WindowStyle Normal
}

function Show-Menu {
    Write-Host "Select services to start:" -ForegroundColor White
    Write-Host ""
    Write-Host "  [1] Backend only" -ForegroundColor White
    Write-Host "  [2] Frontend only" -ForegroundColor White
    Write-Host "  [3] Desktop Pet only" -ForegroundColor White
    Write-Host "  [4] Backend + Frontend" -ForegroundColor White
    Write-Host "  [5] All (Backend + Frontend + Pet)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [S] Refresh status" -ForegroundColor Yellow
    Write-Host "  [Q] Quit" -ForegroundColor Yellow
    Write-Host ""
}

Get-ServiceStatus

while ($true) {
    Show-Menu
    $choice = Read-Host "Enter option"

    switch -Regex ($choice) {
        "^[0Qq]$" {
            Write-Host "Exited" -ForegroundColor Gray
            exit 0
        }
        "^[Ss]$" {
            Get-ServiceStatus
            continue
        }
        "^1$" {
            Start-Backend
        }
        "^2$" {
            Start-Frontend
        }
        "^3$" {
            Start-Pet
        }
        "^4$" {
            Start-Backend
            Start-Frontend
        }
        "^5$" {
            Start-Backend
            Start-Frontend
            Start-Pet
        }
        default {
            Write-Host "Invalid option, starting all..." -ForegroundColor Yellow
            Start-Backend
            Start-Frontend
            Start-Pet
        }
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "   Service URLs" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Backend API:  http://127.0.0.1:8000" -ForegroundColor Cyan
    Write-Host "  API Docs:     http://127.0.0.1:8000/docs" -ForegroundColor Cyan
    Write-Host "  Frontend:      http://localhost:5173" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press any key to return to menu..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
