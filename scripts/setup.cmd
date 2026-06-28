@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
REM Настройка StT: venv с Python внутри venv\_base_python.
REM   scripts\setup.cmd
REM   scripts\setup.cmd --recreate

set "RECREATE="
if /i "%~1"=="--recreate" set "RECREATE=1"

echo ========================================
echo Clerkonator - настройка
echo ========================================
echo.

cd /d "%~dp0.."
set "ROOT=%CD%"
echo [INFO] Корень: %ROOT%
echo.

set "PY_EXE="
set "PY_VER="

where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%V in ('py -3 -c "import sys; print(sys.version.split()[0])" 2^>nul') do set "PY_VER=%%V"
    if defined PY_VER (
        for /f "delims=" %%E in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%E"
        goto :py_ok
    )
)

python --version >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%V in ('python -c "import sys; print(sys.version.split()[0])" 2^>nul') do set "PY_VER=%%V"
    for /f "delims=" %%E in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%E"
)

:py_ok
if defined RECREATE (
    if exist "%ROOT%\venv" (
        echo [INFO] --recreate: удаление venv...
        rmdir /s /q "%ROOT%\venv"
    )
)

if exist "%ROOT%\venv\Scripts\activate.bat" (
    if not defined RECREATE (
        call "%ROOT%\venv\Scripts\activate.bat"
        python --version >nul 2>&1
        if not errorlevel 1 (
            echo [OK] venv уже работает
            goto :install_deps
        )
        echo [WARN] venv не запускается. Пересоздайте: scripts\setup.cmd --recreate
        pause
        exit /b 1
    )
)

if not defined PY_EXE (
    echo [ERROR] Python 3.8+ нужен для первого создания venv
    pause
    exit /b 1
)

echo [OK] Создание venv: %PY_EXE%
"%PY_EXE%" -m venv --copies "%ROOT%\venv"
if errorlevel 1 exit /b 1

echo [INFO] Упаковка Python в venv\_base_python...
"%PY_EXE%" "%ROOT%\scripts\bundle_venv_python.py" "%ROOT%"
if errorlevel 1 exit /b 1

call "%ROOT%\venv\Scripts\activate.bat"
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] venv не запускается
    pause
    exit /b 1
)

:install_deps
echo [INFO] pip + requirements...
python -m pip install --upgrade pip --quiet
python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.org:443 --trusted-host files.pythonhosted.org:443 -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Ошибка установки зависимостей
    pause
    exit /b 1
)

if exist "%ROOT%\requirements-server.txt" (
    echo [INFO] Зависимости STT-сервера ^(GPU Whisper^)...
    python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.org:443 --trusted-host files.pythonhosted.org:443 -r requirements-server.txt
    if errorlevel 1 (
        echo [WARN] Не удалось установить faster-whisper. GPU-сервер: pip install -r requirements-server.txt
    )
)

echo [INFO] Проверка модели Vosk...
if not exist "%ROOT%\models\vosk-model-ru-0.42" (
    if exist "%ROOT%\models\vosk-model-ru-0.42.zip" (
        powershell -NoProfile Expand-Archive -Path "%ROOT%\models\vosk-model-ru-0.42.zip" -DestinationPath "%ROOT%\models\"
    ) else (
        echo [WARN] Модель скачается при первом запуске
    )
) else (
    echo [OK] Модель Vosk на месте
)

if not exist "%ROOT%\data\recordings" mkdir "%ROOT%\data\recordings"
if not exist "%ROOT%\data\transcriptions" mkdir "%ROOT%\data\transcriptions"

echo.
echo [OK] Готово: %ROOT%\venv\
echo [INFO] Для переноса копируйте всю папку проекта (venv с _base_python).
echo.
pause
exit /b 0
