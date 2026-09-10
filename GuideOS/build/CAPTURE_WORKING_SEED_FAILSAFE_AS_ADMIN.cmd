@echo off
setlocal
title Capture verified GuideOS seed failsafe

net session >nul 2>&1
if not "%errorlevel%"=="0" (
  powershell.exe -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
  exit /b
)

cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0capture-working-seed-failsafe.ps1"
set "CAPTURE_EXIT=%ERRORLEVEL%"
echo.
if not "%CAPTURE_EXIT%"=="0" (
  echo Failsafe capture did not complete successfully.
) else (
  echo Failsafe capture and independent verification completed successfully.
)
echo.
pause
exit /b %CAPTURE_EXIT%
