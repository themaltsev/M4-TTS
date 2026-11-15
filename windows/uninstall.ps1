param([switch]$KeepConfig)
$ErrorActionPreference = 'Stop'
$app = Join-Path $env:LOCALAPPDATA 'selected-text-speech'
$configDir = Join-Path $env:APPDATA 'selected-text-speech'
$startupEntry = Join-Path ([Environment]::GetFolderPath('Startup')) 'Selected Text Speech.cmd'
$bin = Join-Path $app 'bin'
$speech = Join-Path $app 'speech.py'
$python = Join-Path $app 'venv\Scripts\python.exe'
$state = Join-Path $app 'state'

if ((Test-Path $python) -and (Test-Path $speech)) {
    & $python $speech stop | Out-Null
}

$trayPidFile = Join-Path $state 'tray.pid'
if (Test-Path $trayPidFile) {
    $trayPid = 0
    [void][int]::TryParse((Get-Content $trayPidFile -Raw), [ref]$trayPid)
    if ($trayPid -gt 0) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $trayPid" -ErrorAction SilentlyContinue
        if ($process -and $process.CommandLine -like "*$speech*tray*") {
            Stop-Process -Id $trayPid -Force -ErrorAction SilentlyContinue
            Wait-Process -Id $trayPid -Timeout 5 -ErrorAction SilentlyContinue
        }
    }
}
Remove-Item $startupEntry -Force -ErrorAction SilentlyContinue

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$filteredPath = ($userPath -split ';' | Where-Object { $_ -and $_.TrimEnd('\') -ne $bin.TrimEnd('\') }) -join ';'
[Environment]::SetEnvironmentVariable('Path', $filteredPath, 'User')

if (-not $KeepConfig) {
    Remove-Item $configDir -Recurse -Force -ErrorAction SilentlyContinue
}
Remove-Item $app -Recurse -Force -ErrorAction SilentlyContinue
if ($KeepConfig) {
    Write-Host "Утилита удалена; конфигурация сохранена: $configDir"
} else {
    Write-Host 'Утилита и её конфигурация удалены.'
}
