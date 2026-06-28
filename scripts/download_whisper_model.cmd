@echo off
chcp 65001 >nul 2>&1
REM Скачать модель Whisper заранее (до запуска сервера)

cd /d "%~dp0.."
call "%~dp0_stt_venv.cmd"
if errorlevel 1 (
    pause
    exit /b 1
)

echo [INFO] Скачивание модели Whisper (faster-whisper)...
echo [INFO] Имя модели берётся из config.server.json ^(stt.server.whisper_model^)
echo [INFO] или config.client.json ^(stt.local.whisper_model^) при --profile client.
echo [INFO] По умолчанию: large-v3-turbo ^(~1.6 ГБ^). Список: --list
echo.
python scripts\download_whisper_model.py %*
pause
