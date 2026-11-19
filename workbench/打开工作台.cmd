@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0open-workbench.ps1" %*
if errorlevel 1 (
  echo Workbench could not start. Please review the error above.
  pause
  exit /b 1
)
