@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply-media-trust-to-seed-disk4.ps1"
if errorlevel 1 pause
