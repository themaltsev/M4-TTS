$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$app = Join-Path $env:LOCALAPPDATA 'selected-text-speech'
$configDir = Join-Path $env:APPDATA 'selected-text-speech'
$bin = Join-Path $app 'bin'
$venv = Join-Path $app 'venv'

New-Item -ItemType Directory -Force -Path $bin, $configDir | Out-Null
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
    py -3 -m venv $venv
}
$python = Join-Path $venv 'Scripts\python.exe'
& $python -m pip install edge-tts pygame keyboard
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
'@ | Set-Content -Encoding utf8 (Join-Path $configDir 'config.env')
}

$commandsToCreate = @{
    'speak.cmd' = 'speak'
    'speak-selection.cmd' = 'selection'
    'stop-speech.cmd' = 'stop'
    'speak-status.cmd' = 'status'
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
$hotkey = Join-Path $startup 'Selected Text Speech.cmd'
"@echo off`r`nstart `"Selected Text Speech hotkey`" /min `"$python`" `"$app\speech.py`" hotkey`r`n" | Set-Content -Encoding ascii $hotkey

Write-Host "Установлено в $app"
Write-Host "Команды: $bin\speak.cmd TEXT, speak-selection.cmd, stop-speech.cmd, speak-status.cmd"
Write-Host 'Хоткей Ctrl+Alt+S активируется после входа в Windows; Ctrl+Alt+Q завершает его.'
Write-Host 'Чтобы использовать собственный хоткей, назначь speak-selection.cmd в настройках ярлыка.'
