@echo off
setlocal
cd /d "%~dp0"
python -m unittest -v test_guide_node.py test_media_library.py || exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --windowed --name GuideNode guide_node_gui.py || exit /b 1
echo.
echo Built: %CD%\dist\GuideNode.exe
endlocal
