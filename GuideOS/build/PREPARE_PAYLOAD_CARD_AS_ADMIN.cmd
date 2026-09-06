@echo off
title GuideOS Format 0 payload card preparation
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare-payload-card-disk4.ps1"
set "PREPARE_EXIT=%ERRORLEVEL%"
echo.
type "%~dp0prepare-payload-card-result.txt" 2>nul
echo.
if not "%PREPARE_EXIT%"=="0" (
  echo Payload card preparation did not complete successfully.
) else (
  echo GuideOS payload card prepared and verified successfully.
)
echo.
pause
