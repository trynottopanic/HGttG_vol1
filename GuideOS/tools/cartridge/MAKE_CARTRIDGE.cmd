@echo off
setlocal
title Guide Cartridge Workshop
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-CartridgeWorkshop.ps1"
if errorlevel 1 (
  echo.
  echo The cartridge was not made. The explanation is shown above.
)
echo.
pause

