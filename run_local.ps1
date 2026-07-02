# =========================================================
#   KODARI CAD SaaS MVP LOCAL LAUNCHER
#         - 코다리 부장 로컬 기동기 - 
# =========================================================

# 한글 깨짐 방지를 위해 콘솔 출력 인코딩을 UTF-8로 강제 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Clear-Host
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "   충성! 대표님, 코다리 개발부장입니다!" -ForegroundColor Yellow
Write-Host "   로컬에서 Docker/Redis 없이 원터치 기동 가능한 하네스를 완비했습니다!" -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Cyan

# 1. 포트 확인 및 정리 (기존 프로세스 잔존 대비 - Netstat 활용 초고속 논블로킹 방식)
Write-Host "[*] 기존 백엔드(8000) 및 프론트엔드(3000) 포트 점유 상태를 체크합니다..." -ForegroundColor Gray

# 8000 포트 정리
$proc8000 = netstat -ano | Select-String ":8000\s+"
if ($proc8000) {
    foreach ($line in $proc8000) {
        $parts = $line -split '\s+' | Where-Object { $_ }
        $pid = $parts[-1]
        if ($pid -and $pid -ne "0" -and $pid -ne $PID) {
            try {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                Write-Host "[+] 8000 포트를 점유 중이던 기존 프로세스(PID: $pid)를 정리했습니다." -ForegroundColor DarkYellow
            } catch {}
        }
    }
}

# 3000 포트 정리
$proc3000 = netstat -ano | Select-String ":3000\s+"
if ($proc3000) {
    foreach ($line in $proc3000) {
        $parts = $line -split '\s+' | Where-Object { $_ }
        $pid = $parts[-1]
        if ($pid -and $pid -ne "0" -and $pid -ne $PID) {
            try {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                Write-Host "[+] 3000 포트를 점유 중이던 기존 프로세스(PID: $pid)를 정리했습니다." -ForegroundColor DarkYellow
            } catch {}
        }
    }
}

# 2. 백엔드 실행
Write-Host "[*] FastAPI 백엔드 API 서버를 새 창에서 기동합니다..." -ForegroundColor Cyan
Write-Host "    -> 주소: http://127.0.0.1:8000" -ForegroundColor Gray
Write-Host "    -> Redis 미검출 시, Eager 모드(In-Memory)로 자동 작동합니다! (서킷 브레이커)" -ForegroundColor Green
Start-Process PowerShell "-NoExit -Command python -m uvicorn app.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory $PSScriptRoot

# 3. 프론트엔드 실행
Write-Host "[*] Next.js 프론트엔드 서버를 새 창에서 기동합니다..." -ForegroundColor Cyan
Write-Host "    -> 주소: http://localhost:3000" -ForegroundColor Gray
Start-Process PowerShell "-NoExit -Command npm run dev" -WorkingDirectory "$PSScriptRoot\web"

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "   [완료] 백엔드와 프론트엔드 새 터미널 창을 기동 완료했습니다!" -ForegroundColor Green
Write-Host "   대표님! 이제 크롬 브라우저에서 아래 주소로 즉시 접근하시면 됩니다:" -ForegroundColor Yellow
Write-Host "   👉 http://localhost:3000" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Cyan

