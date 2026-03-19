$ErrorActionPreference = "Stop"

[Console]::InputEncoding = [System.Text.UTF8Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::UTF8
$env:PYTHONUTF8 = "1"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$python = "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path $python)) {
    $python = "py"
}

$logsDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logsDir "main_$timestamp.log"

Write-Host "===================================================="
Write-Host "Paper push runner starting..."
Write-Host "Start time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "Log file: $logPath"
Write-Host "===================================================="
Write-Host ""

if ($python -eq "py") {
    & py -3 -u main.py @args 2>&1 | Tee-Object -FilePath $logPath
} else {
    & $python -u main.py @args 2>&1 | Tee-Object -FilePath $logPath
}

$exitCode = $LASTEXITCODE
Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "[OK] main.py finished successfully."
} else {
    Write-Host "[ERROR] main.py failed. Check the terminal output or log file."
}

exit $exitCode
