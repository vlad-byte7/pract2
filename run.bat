@echo off
py -3 --version >nul 2>&1
if errorlevel 1 (
    python "%~dp0src\main.py" %*
) else (
    py -3 "%~dp0src\main.py" %*
)
exit /b %errorlevel%
