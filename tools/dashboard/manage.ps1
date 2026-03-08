# manage.ps1
# IbbyTech Dashboard — process manager
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File manage.ps1 start
#   powershell -ExecutionPolicy Bypass -File manage.ps1 stop
#   powershell -ExecutionPolicy Bypass -File manage.ps1 restart
#   powershell -ExecutionPolicy Bypass -File manage.ps1 status
#
# Short form (from the dashboard directory):
#   .\manage.ps1 start | stop | restart | status

param (
    [Parameter(Position=0)]
    [ValidateSet('start','stop','restart','status')]
    [string]$Command = 'status'
)

$PORT       = 8000
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PID_FILE   = Join-Path $SCRIPT_DIR '.dashboard.pid'
$LOG_FILE   = Join-Path $SCRIPT_DIR 'dashboard.log'

# ── Helpers ───────────────────────────────────────────────────────────────────

function Get-StoredPid {
    if (Test-Path $PID_FILE) {
        $raw = Get-Content $PID_FILE -Raw
        $n   = [int]($raw.Trim())
        return $n
    }
    return $null
}

function Test-ProcessAlive {
    param([int]$Id)
    try {
        $p = Get-Process -Id $Id -ErrorAction Stop
        return (-not $p.HasExited)
    } catch {
        return $false
    }
}

function Get-PortOwner {
    $conns = Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue
    if ($conns) {
        return ($conns | Select-Object -ExpandProperty OwningProcess -Unique | Select-Object -First 1)
    }
    return $null
}

function Kill-Tree {
    param([int]$Id)
    # taskkill /T kills the process AND all child processes (covers uvicorn --reload workers)
    $result = & taskkill /PID $Id /F /T 2>&1
    return $result
}

function Wait-PortFree {
    param([int]$Seconds = 5)
    for ($i = 0; $i -lt $Seconds; $i++) {
        if (-not (Get-PortOwner)) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Wait-PortOpen {
    param([int]$Seconds = 10)
    for ($i = 0; $i -lt $Seconds; $i++) {
        if (Get-PortOwner) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

# ── Commands ──────────────────────────────────────────────────────────────────

function Invoke-Status {
    $storedPid  = Get-StoredPid
    $portOwner  = Get-PortOwner

    Write-Host ""
    Write-Host "  IbbyTech Dashboard — status" -ForegroundColor Cyan
    Write-Host "  ────────────────────────────"

    if ($storedPid -and (Test-ProcessAlive $storedPid)) {
        Write-Host "  Status  : RUNNING" -ForegroundColor Green
        Write-Host "  PID     : $storedPid"
        Write-Host "  URL     : http://localhost:$PORT"
        Write-Host "  Log     : $LOG_FILE"
    } elseif ($portOwner) {
        Write-Host "  Status  : RUNNING (untracked — PID $portOwner owns port $PORT)" -ForegroundColor Yellow
        Write-Host "  PID file: not found or stale"
        Write-Host "  URL     : http://localhost:$PORT"
    } else {
        Write-Host "  Status  : STOPPED" -ForegroundColor DarkGray
        if ($storedPid) {
            Write-Host "  Note    : stale PID file found (PID $storedPid no longer alive)" -ForegroundColor DarkGray
        }
    }
    Write-Host ""
}

function Invoke-Stop {
    $storedPid = Get-StoredPid
    $portOwner = Get-PortOwner

    # Kill by PID file first
    if ($storedPid) {
        if (Test-ProcessAlive $storedPid) {
            Write-Host "  Stopping PID $storedPid (process tree)..." -ForegroundColor Yellow
            Kill-Tree $storedPid | Out-Null
        } else {
            Write-Host "  PID $storedPid is no longer alive (stale PID file)." -ForegroundColor DarkGray
        }
        Remove-Item $PID_FILE -Force -ErrorAction SilentlyContinue
    }

    # Kill any untracked process still holding the port
    $portOwner = Get-PortOwner
    if ($portOwner -and $portOwner -ne $storedPid) {
        Write-Host "  Killing untracked PID $portOwner on port $PORT..." -ForegroundColor Yellow
        Kill-Tree $portOwner | Out-Null
    }

    if (Wait-PortFree) {
        Write-Host "  Stopped. Port $PORT is now free." -ForegroundColor Green
    } else {
        Write-Host "  WARNING: port $PORT still in use after stop attempt." -ForegroundColor Red
    }
}

function Invoke-Start {
    # Ensure port is clear before starting
    $portOwner = Get-PortOwner
    if ($portOwner) {
        Write-Host "  Port $PORT is in use (PID $portOwner). Stopping first..." -ForegroundColor Yellow
        Invoke-Stop
    }

    # Verify uvicorn is available
    $uvicorn = Get-Command uvicorn -ErrorAction SilentlyContinue
    if (-not $uvicorn) {
        Write-Host "  ERROR: uvicorn not found. Activate your venv first." -ForegroundColor Red
        exit 1
    }

    Write-Host "  Starting dashboard (background)..." -ForegroundColor Cyan
    Write-Host "  Log: $LOG_FILE"

    # Start uvicorn as a detached background process; redirect output to log file
    $proc = Start-Process `
        -FilePath       $uvicorn.Source `
        -ArgumentList   @("app:app", "--reload", "--port", "$PORT") `
        -WorkingDirectory $SCRIPT_DIR `
        -RedirectStandardOutput $LOG_FILE `
        -RedirectStandardError  ($LOG_FILE -replace '\.log$', '.err.log') `
        -PassThru `
        -WindowStyle Hidden

    if (-not $proc) {
        Write-Host "  ERROR: failed to start uvicorn." -ForegroundColor Red
        exit 1
    }

    # Save the launcher PID
    $proc.Id | Out-File $PID_FILE -Force

    # Wait for the port to open
    if (Wait-PortOpen -Seconds 12) {
        Write-Host "  STARTED — PID $($proc.Id) | http://localhost:$PORT" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: port $PORT did not open within 12 seconds." -ForegroundColor Yellow
        Write-Host "  Check log: $LOG_FILE" -ForegroundColor Yellow
    }
}

# ── Main ──────────────────────────────────────────────────────────────────────

Write-Host ""
switch ($Command) {
    'start'   { Invoke-Start }
    'stop'    { Invoke-Stop  }
    'restart' { Invoke-Stop; Write-Host ""; Invoke-Start }
    'status'  { Invoke-Status }
}
Write-Host ""
