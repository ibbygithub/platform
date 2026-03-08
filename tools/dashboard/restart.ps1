# restart.ps1
# Kill any process holding port 8000 and restart the dashboard uvicorn server.
# Run from anywhere: powershell -ExecutionPolicy Bypass -File C:\git\work\platform\tools\dashboard\restart.ps1

$PORT     = 8000
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "--- IbbyTech Dashboard Restart ---"

# ── Kill any process on port 8000 ─────────────────────────────────────────
$connections = Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue
if ($connections) {
    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $pids) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Killing PID $pid ($($proc.ProcessName)) on port $PORT..."
            Stop-Process -Id $pid -Force
        }
    }
    Start-Sleep -Milliseconds 500
} else {
    Write-Host "No process found on port $PORT."
}

# ── Verify port is free ───────────────────────────────────────────────────
$still = Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue
if ($still) {
    Write-Host "ERROR: Port $PORT is still in use. Cannot start server." -ForegroundColor Red
    exit 1
}

# ── Start uvicorn ─────────────────────────────────────────────────────────
Write-Host "Starting dashboard on http://localhost:$PORT ..."
Set-Location $SCRIPT_DIR
uvicorn app:app --reload --port $PORT
