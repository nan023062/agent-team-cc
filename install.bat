@echo off
chcp 65001 >nul
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found.
    echo  Install Python 3.10+ and make sure it is on PATH.
    echo.
    pause
    exit /b 1
)
python "%~dp0install.py"
pause
