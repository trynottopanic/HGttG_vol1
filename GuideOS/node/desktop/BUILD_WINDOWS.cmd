@echo off
setlocal
cd /d "%~dp0"
python -m unittest discover -v -p "test_*.py" || exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --windowed --name GuideNode guide_node_native_gui.py || exit /b 1
echo.
echo Built: %CD%\dist\GuideNode.exe
endlocal
