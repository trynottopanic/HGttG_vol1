@echo off
setlocal
title Install Bluetooth and playback update on GuideOS seed

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  powershell.exe -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
  exit /b
)

cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply-bluetooth-music-apps-to-seed-disk4.ps1"
set "APPLY_EXIT=%ERRORLEVEL%"
echo.
if not "%APPLY_EXIT%"=="0" (
  echo The Bluetooth and playback update did not complete successfully.
  echo The verified failsafe image remains unchanged.
) else (
  echo The Bluetooth and playback update was written and independently verified.
)
echo.
pause
exit /b %APPLY_EXIT%
