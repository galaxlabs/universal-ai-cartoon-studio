@echo off
setlocal
title Universal AI Cartoon Studio
set "STUDIO_PYTHON=%~dp0.venv-windows\Scripts\python.exe"
if not exist "%STUDIO_PYTHON%" set "STUDIO_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%STUDIO_PYTHON%" (
    echo The Windows Python environment is missing.
    echo Please see START_HERE_UR.md in this project folder.
    pause
    exit /b 1
)
"%STUDIO_PYTHON%" "%~dp0scripts\launch_studio.py"
set "STUDIO_EXIT=%ERRORLEVEL%"
if not "%STUDIO_EXIT%"=="0" (
    echo.
    echo Studio could not start. Please share the message above.
    pause
)
exit /b %STUDIO_EXIT%
