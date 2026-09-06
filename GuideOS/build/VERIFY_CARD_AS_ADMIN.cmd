@echo off
title GuideOS card verification
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-ddr3-disk4.ps1" > "%~dp0verify-ddr3-user-result.txt" 2>&1
set "VERIFY_EXIT=%ERRORLEVEL%"
type "%~dp0verify-ddr3-user-result.txt"
echo.
if not "%VERIFY_EXIT%"=="0" (
  echo Verification did not complete successfully.
) else (
  echo Verification completed successfully.
)
echo.
pause
