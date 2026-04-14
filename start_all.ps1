$Host.UI.RawUI.WindowTitle = "Music7ox"
$ProjectRoot = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Music7ox - Quick Start" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

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

Write-Host "[Start] Backend..." -ForegroundColor Green
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot'; python -m api.main" -WindowStyle Normal
Start-Sleep -Seconds 3

Write-Host "[Start] Frontend..." -ForegroundColor Green
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot\frontend'; npm run dev" -WindowStyle Normal
Start-Sleep -Seconds 2

Write-Host "[Start] Desktop Pet..." -ForegroundColor Green
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot\desktop_pet'; npm start" -WindowStyle Normal

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Service URLs" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Backend API:  http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "  API Docs:     http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  Frontend:     http://localhost:5173" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Start-Sleep -Seconds 3

$backend = Test-Port -Port 8000
$frontend = Test-Port -Port 5173

Write-Host "Service Status:" -ForegroundColor Yellow
Write-Host "  Backend (8000): " -NoNewline
if ($backend) { Write-Host "Running" -ForegroundColor Green } else { Write-Host "Starting..." -ForegroundColor Yellow }
Write-Host "  Frontend (5173): " -NoNewline
if ($frontend) { Write-Host "Running" -ForegroundColor Green } else { Write-Host "Starting..." -ForegroundColor Yellow }
Write-Host ""
Write-Host "All services started!" -ForegroundColor Green
