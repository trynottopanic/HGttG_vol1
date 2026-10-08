@echo off
setlocal
set "SE_DIR=%~dp0"
set "SE_SERVER=%SE_DIR%runtime\llama-b10516-vulkan\llama-server.exe"
set "SE_MODEL=%SE_DIR%models\Qwen3-8B-Q4_K_M.gguf"

if not exist "%SE_SERVER%" (
  echo The local llama.cpp runtime is missing.
  echo Expected: %SE_SERVER%
  pause
  exit /b 1
)
if not exist "%SE_MODEL%" (
  echo The local model is missing.
  echo Expected: %SE_MODEL%
  pause
  exit /b 1
)

echo Starting the Guide Semiotic Engine locally.
echo Closing this window safely stops the Engine.
python "%SE_DIR%guide_se_service.py" --backend llama-cpp --llama-server "%SE_SERVER%" --model "%SE_MODEL%"
if errorlevel 1 (
  echo.
  echo The Semiotic Engine stopped because of an error.
  pause
)
endlocal
