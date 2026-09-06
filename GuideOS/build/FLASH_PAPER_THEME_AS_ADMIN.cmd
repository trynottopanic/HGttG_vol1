@echo off
title Install GuideOS Paper Theme 0
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0flash-paper-theme-rootfs-disk4.ps1"
set "FLASH_EXIT=%ERRORLEVEL%"
echo.
type "%~dp0flash-paper-theme-rootfs-result.txt" 2>nul
echo.
if not "%FLASH_EXIT%"=="0" (
  echo Theme installation did not complete successfully.
) else (
  echo Theme installation and verification completed successfully.
)
echo.
pause
