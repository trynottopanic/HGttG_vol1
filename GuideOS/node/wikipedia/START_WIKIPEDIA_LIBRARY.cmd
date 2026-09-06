@echo off
setlocal
title GuideOS Wikipedia Library
echo.
echo GUIDE WIKIPEDIA LIBRARY
echo This stores current English Wikipedia article text on this computer.
echo It does not include article history, pictures, or video.
echo.
set /p "GUIDE_LIBRARY_DEST=Storage folder (example G:\Guide-Library\Wikipedia): "
if not defined GUIDE_LIBRARY_DEST goto :cancel
echo.
echo [P] Plan only   [D] Download/resume   [S] Status   [V] Verify   [Q] Quit
choice /c PDSVQ /n /m "Choose: "
if errorlevel 5 goto :end
if errorlevel 4 goto :verify
if errorlevel 3 goto :status
if errorlevel 2 goto :download
set "GUIDE_LIBRARY_ACTION=plan"
goto :run
:verify
set "GUIDE_LIBRARY_ACTION=verify"
goto :run
:status
set "GUIDE_LIBRARY_ACTION=status"
goto :run
:download
set "GUIDE_LIBRARY_ACTION=download"
:run
echo.
where py >nul 2>nul
if errorlevel 1 (
  python "%~dp0guide_wikipedia_dump.py" %GUIDE_LIBRARY_ACTION% "%GUIDE_LIBRARY_DEST%"
) else (
  py -3 "%~dp0guide_wikipedia_dump.py" %GUIDE_LIBRARY_ACTION% "%GUIDE_LIBRARY_DEST%"
)
echo.
pause
goto :end
:cancel
echo No folder was entered. Nothing changed.
pause
:end
endlocal
