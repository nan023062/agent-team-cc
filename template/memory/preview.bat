@echo off
chcp 65001 >nul
set "VENV=%~dp0..\.venv\Scripts\python.exe"
if exist "%VENV%" (
    "%VENV%" "%~dp0preview.py"
) else (
    python "%~dp0preview.py"
)
