@echo off
title GuideOS HELLO WORLD root filesystem update
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0patch-hello-world-rootfs-disk4.ps1"
set "PATCH_EXIT=%ERRORLEVEL%"
echo.
type "%~dp0patch-hello-world-rootfs-result.txt" 2>nul
echo.
if not "%PATCH_EXIT%"=="0" (
  echo The update did not complete successfully.
) else (
  echo The HELLO WORLD update and verification completed successfully.
)
echo.
pause
