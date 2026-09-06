@echo off
title GuideOS Node Link seed update
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply-node-link-to-seed-disk4.ps1"
echo.
type "%~dp0apply-node-link-to-seed-result.txt" 2>nul
echo.
pause
