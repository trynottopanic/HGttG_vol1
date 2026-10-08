@echo off
setlocal
cd /d "%~dp0"
python -m unittest discover -v -p "test_*.py" || exit /b 1
python -m PyInstaller --noconfirm --clean GuideSemioticEngine.spec || exit /b 1
echo.
echo Built: %CD%\dist\GuideSemioticEngine.exe
echo Keep the models and runtime folders beside the dist folder.
endlocal
