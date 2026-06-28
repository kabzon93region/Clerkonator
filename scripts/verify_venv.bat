@echo off
chcp 65001 >nul 2>&1
REM Проверка venv StT — scripts\verify_venv.bat

setlocal enabledelayedexpansion
cd /d "%~dp0.."
set "ROOT=%CD%"

echo ========================================
echo ПРОВЕРКА ОКРУЖЕНИЯ StT
echo ========================================
echo [INFO] Корень: %ROOT%
echo.

call "%~dp0_stt_venv.cmd"
if errorlevel 1 goto :fail

for /f "delims=" %%V in ('python --version 2^>^&1') do echo [OK] %%V ^(venv^)

if exist "%ROOT%\venv\_base_python\python.exe" (
    echo [OK] Python упакован: venv\_base_python
) else (
    echo [WARN] venv\_base_python не найден — выполните scripts\setup.cmd
)

python -c "import vosk, pyaudio, pystray; print('[OK] vosk, pyaudio, pystray')" 2>nul
if errorlevel 1 (
    echo [ERROR] Не все зависимости установлены
    goto :fail
)

python -c "import tkinter; tkinter.Tk().destroy(); print('[OK] tkinter')" 2>nul
if errorlevel 1 (
    echo [ERROR] tkinter/Tcl не работает — scripts\setup.cmd --recreate
    goto :fail
)

echo.
echo [OK] Проверка завершена
pause
exit /b 0

:fail
echo [ERROR] Проверка завершилась с ошибкой
pause
exit /b 1
