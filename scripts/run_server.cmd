@echo off
chcp 65001 >nul 2>&1
REM STT Server — scripts\run_server.cmd

cd /d "%~dp0.."
call "%~dp0_stt_venv.cmd"
if errorlevel 1 (
    pause
    exit /b 1
)

echo [INFO] STT Server — загрузка модели и HTTP-сервера...
echo [INFO] GPU: первый запуск скачивает Whisper в models\whisper\ (по умолчанию large-v3-turbo ~1.6 ГБ).
echo [INFO] Заранее: download_whisper_model.cmd
echo [INFO] Адреса для клиентов появятся в логе ниже.
echo [INFO] Сервер запущен с иконкой в трее (--silent скрывает консоль).
echo.

python stt\server_app.py --host 0.0.0.0 --port 8765 --silent
pause
