$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'windows\install.ps1') @args
if (-not $?) { exit 1 }
exit 0
