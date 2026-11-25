@echo off
setlocal
py -3 --version >nul 2>&1
if errorlevel 1 (
    python "%~dp0src\main.py" %*
) else (
    py -3 "%~dp0src\main.py" %*
)
set "result=%errorlevel%"
if "%~1"=="" pause
exit /b %result%
