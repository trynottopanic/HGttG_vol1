@echo off
title Capture known-working muOS boot reference
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0capture-muos-reference.ps1" > "%~dp0capture-muos-reference-user-output.txt" 2>&1
set "CAPTURE_EXIT=%ERRORLEVEL%"
type "%~dp0capture-muos-reference-user-output.txt"
echo.
if not "%CAPTURE_EXIT%"=="0" (
  echo Reference capture did not complete successfully.
) else (
  echo Reference capture completed successfully.
)
echo.
pause
