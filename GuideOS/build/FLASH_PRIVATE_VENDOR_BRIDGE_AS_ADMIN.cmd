@echo off
title GuideOS private RG35XX H seed flash
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0flash-private-vendor-bridge-disk4.ps1"
set "FLASH_EXIT=%ERRORLEVEL%"
echo.
type "%~dp0flash-private-vendor-bridge-result.txt" 2>nul
echo.
if not "%FLASH_EXIT%"=="0" (
  echo Flashing did not complete successfully.
) else (
  echo Flashing and verification completed successfully.
)
echo.
pause
