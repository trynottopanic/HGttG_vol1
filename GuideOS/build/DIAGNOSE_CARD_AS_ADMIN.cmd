@echo off
title GuideOS card comparison
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0diagnose-ddr3-card.ps1" > "%~dp0diagnose-ddr3-user-output.txt" 2>&1
set "DIAG_EXIT=%ERRORLEVEL%"
type "%~dp0diagnose-ddr3-user-output.txt"
echo.
if not "%DIAG_EXIT%"=="0" (
  echo Card comparison did not complete successfully.
) else (
  echo Card comparison completed successfully.
)
echo.
pause
