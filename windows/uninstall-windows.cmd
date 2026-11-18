@echo off
setlocal
for %%U in ("%~dp0unins*.exe") do (
  if exist "%%~fU" (
    start "" "%%~fU"
    exit /b 0
  )
)
echo Не найден стандартный uninstaller Selected Text Speech.
echo Откройте Параметры Windows ^> Приложения ^> Установленные приложения.
exit /b 1
