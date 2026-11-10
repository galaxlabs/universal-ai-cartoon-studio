@echo off
setlocal
title Universal AI Cartoon Studio - Windows Setup
where uv >nul 2>nul
if errorlevel 1 (
    echo The uv package manager is required for first-time setup.
    echo Install uv from https://docs.astral.sh/uv/getting-started/installation/
    echo Then double-click this file again. No administrator service is installed here.
    pause
    exit /b 1
)
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "UV_PROJECT_ENVIRONMENT=%~dp0.venv-windows"
set "UV_PYTHON_INSTALL_DIR=%~dp0.python"
echo Preparing Python 3.13 and the exact dependencies from uv.lock...
echo First-time setup may download Python and locked packages from the internet.
uv sync --frozen --python 3.13
set "STUDIO_EXIT=%ERRORLEVEL%"
popd
if not "%STUDIO_EXIT%"=="0" (
    echo Setup did not complete. Share the error above, without any private token.
    pause
    exit /b %STUDIO_EXIT%
)
echo Setup complete. Double-click Start Studio.cmd to launch the application.
pause
exit /b 0
