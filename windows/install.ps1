$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$app = Join-Path $env:LOCALAPPDATA 'selected-text-speech'
$configDir = Join-Path $env:APPDATA 'selected-text-speech'
$bin = Join-Path $app 'bin'
$venv = Join-Path $app 'venv'

New-Item -ItemType Directory -Force -Path $bin, $configDir | Out-Null
$state = Join-Path $app 'state'
$oldTrayPidFile = Join-Path $state 'tray.pid'
if (Test-Path $oldTrayPidFile) {
    $oldTrayPid = 0
    [void][int]::TryParse((Get-Content $oldTrayPidFile -Raw), [ref]$oldTrayPid)
    if ($oldTrayPid -gt 0) {
        $oldTray = Get-CimInstance Win32_Process -Filter "ProcessId = $oldTrayPid" -ErrorAction SilentlyContinue
        if ($oldTray -and $oldTray.CommandLine -like "*selected-text-speech*speech.py*") {
            Stop-Process -Id $oldTrayPid -Force -ErrorAction SilentlyContinue
            Wait-Process -Id $oldTrayPid -Timeout 5 -ErrorAction SilentlyContinue
        }
    }
}
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
    py -3 -m venv $venv
}
$python = Join-Path $venv 'Scripts\python.exe'
& $python -m pip install edge-tts pygame keyboard pystray pillow
Copy-Item (Join-Path $repo 'speech.py') (Join-Path $app 'speech.py') -Force
if (-not (Test-Path (Join-Path $configDir 'config.env'))) {
    @'
EDGE_TTS_VOICE=ru-RU-SvetlanaNeural
EDGE_TTS_RATE=+0%
EDGE_TTS_VOLUME=+0%
EDGE_TTS_PITCH=+0Hz
MPV_PLAYBACK_VOLUME=100
API_MAX_ATTEMPTS=3
API_RETRY_BASE_SECONDS=1.5
API_RETRY_MAX_SECONDS=8
HOTKEY=ctrl+alt+s
'@ | Set-Content -Encoding utf8 (Join-Path $configDir 'config.env')
}
$configFile = Join-Path $configDir 'config.env'
if (-not (Select-String -Path $configFile -Pattern '^\s*HOTKEY\s*=' -Quiet)) {
    Add-Content -Encoding utf8 $configFile 'HOTKEY=ctrl+alt+s'
}

$commandsToCreate = @{
    'speak.cmd' = 'speak'
    'speak-selection.cmd' = 'selection'
    'stop-speech.cmd' = 'stop'
    'speak-status.cmd' = 'status'
    'selected-text-speech-tray.cmd' = 'tray'
}
foreach ($entry in $commandsToCreate.GetEnumerator()) {
    $target = Join-Path $bin $entry.Key
    "@echo off`r`n`"$python`" `"$app\speech.py`" $($entry.Value) %*`r`n" | Set-Content -Encoding ascii $target
}
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($userPath -split ';') -notcontains $bin) {
    [Environment]::SetEnvironmentVariable('Path', (($userPath.TrimEnd(';') + ';' + $bin).Trim(';')), 'User')
}

$startup = [Environment]::GetFolderPath('Startup')
$startupEntry = Join-Path $startup 'Selected Text Speech.cmd'
$pythonw = Join-Path $venv 'Scripts\pythonw.exe'
"@echo off`r`nstart `"Selected Text Speech tray`" `"$pythonw`" `"$app\speech.py`" tray`r`n" | Set-Content -Encoding ascii $startupEntry
$trayArgs = '"{0}" tray' -f (Join-Path $app 'speech.py')
Start-Process -FilePath $pythonw -ArgumentList $trayArgs -WindowStyle Hidden

Write-Host "Установлено в $app"
Write-Host "Команды: $bin\speak.cmd TEXT, speak-selection.cmd, stop-speech.cmd, speak-status.cmd"
Write-Host 'В трее появится таймер, а при воспроизведении — значок эквалайзера.'
Write-Host "Хоткей настраивается через HOTKEY в $configDir\config.env; перезапусти значок после изменения."
Write-Host 'Удаление: запусти windows\uninstall.ps1; ключ -KeepConfig сохранит настройки.'
