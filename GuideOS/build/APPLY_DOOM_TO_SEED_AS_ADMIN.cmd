@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -Verb RunAs -WindowStyle Normal -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0apply-doom-to-seed-disk4.ps1""'"
if errorlevel 1 (
  echo The GuideOS seed update did not complete.
  pause
  exit /b 1
)
echo The GuideOS seed update and verification finished.
pause
