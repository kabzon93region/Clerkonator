@echo off
chcp 65001 >nul 2>&1
REM Клиент Clerkonator — scripts\run.cmd

cd /d "%~dp0.."
call "%~dp0_stt_venv.cmd"
if errorlevel 1 (
    pause
    exit /b 1
)

echo [INFO] Корень: %CD%
echo [INFO] Запуск клиента...
echo Не закрывайте окно — приложение в трее. Без консоли: run_silent.vbs
echo.

python main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Приложение завершилось с ошибкой
    pause
)
