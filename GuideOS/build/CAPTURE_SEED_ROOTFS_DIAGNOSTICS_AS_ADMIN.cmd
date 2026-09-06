@echo off
title GuideOS seed diagnostic capture
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0capture-seed-rootfs-diagnostics.ps1"
set "CAPTURE_EXIT=%ERRORLEVEL%"
echo.
type "%~dp0capture-safe-shutdown-diagnostics-result.txt" 2>nul
echo.
if not "%CAPTURE_EXIT%"=="0" (
  echo Diagnostic capture did not complete successfully.
) else (
  echo Diagnostic root capture completed successfully.
)
echo.
pause
