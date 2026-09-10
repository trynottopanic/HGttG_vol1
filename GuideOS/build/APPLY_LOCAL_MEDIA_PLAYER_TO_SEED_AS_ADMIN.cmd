@echo off
setlocal
fltmc >nul 2>&1
if errorlevel 1 (
  powershell.exe -NoProfile -Command "Start-Process -Verb RunAs -WindowStyle Hidden -FilePath '%~f0'"
  exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply-local-media-player-to-seed-disk4.ps1"
exit /b %errorlevel%
