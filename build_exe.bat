@echo off
setlocal

set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

set PYTHON_EXE=.venv\Scripts\python.exe
if not exist "%PYTHON_EXE%" (
  echo [ERROR] Python not found: %PYTHON_EXE%
  popd
  exit /b 1
)

echo [1/4] Repairing pip (ensurepip)...
"%PYTHON_EXE%" -m ensurepip --upgrade

echo [2/4] Installing build dependencies...
"%PYTHON_EXE%" -m pip install -U pip setuptools wheel pyinstaller rich

echo [3/4] Cleaning old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist traffic_sim.spec del /q traffic_sim.spec

echo [4/4] Building one-file EXE (console + validate only, no gradio)...
"%PYTHON_EXE%" -m PyInstaller ^
  --onefile ^
  --name traffic_sim ^
  run.py

if errorlevel 1 (
  echo [ERROR] Build failed.
  popd
  exit /b 1
)

echo [DONE] EXE generated at dist\traffic_sim.exe
popd
endlocal
