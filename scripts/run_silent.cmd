@echo off
chcp 65001 >nul 2>&1

cd /d "%~dp0.."
call "%~dp0_stt_venv.cmd"
if errorlevel 1 (
    pause
    exit /b 1
)

start "" pythonw main.py
