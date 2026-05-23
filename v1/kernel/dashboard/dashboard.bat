@echo off
chcp 65001 >/dev/null
set "VENV=%~dp0..\..\.venv\Scripts\python.exe"
if exist "%VENV%" (
    "%VENV%" "%~dp0dashboard.py"
) else (
    python "%~dp0dashboard.py"
)
