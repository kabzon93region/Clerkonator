@echo off
chcp 65001 >nul 2>&1
setlocal
REM ============================================
REM Clerkonator — Build Script
REM Builds standalone .exe for Client and Server
REM Requires: pip install pyinstaller
REM ============================================

cd /d "%~dp0"

echo [BUILD] Clerkonator — Build EXE
echo.

REM Check PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

REM Ensure icons exist
python -c "from utils.app_icon import ensure_icon_files, ensure_server_icon_files; ensure_icon_files(); ensure_server_icon_files()"
set CLIENT_ICON=assets\app_icon.ico
set SERVER_ICON=assets\server_icon.ico

REM Create release directory
if not exist release mkdir release

echo.
echo ════════════════════════════════════════════
echo  Building CLIENT...
echo ════════════════════════════════════════════
echo.

pyinstaller --noconfirm --onefile --windowed ^
    --name "Clerkonator-Client" ^
    --icon "%CLIENT_ICON%" ^
    --add-data "assets;assets" ^
    --add-data "config.client.example.json;." ^
    --hidden-import "pynput.keyboard._win32" ^
    --hidden-import "pynput.mouse._win32" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "pygame" ^
    --hidden-import "vosk" ^
    --collect-all "vosk" ^
    main.py

if errorlevel 1 (
    echo [ERROR] Client build FAILED
    pause
    exit /b 1
)

copy /y "dist\Clerkonator-Client.exe" "release\Clerkonator-Client.exe"
echo [OK] Client: release\Clerkonator-Client.exe

echo.
echo ════════════════════════════════════════════
echo  Building SERVER...
echo ════════════════════════════════════════════
echo.

pyinstaller --noconfirm --onefile --windowed ^
    --name "Clerkonator-Server" ^
    --icon "%SERVER_ICON%" ^
    --add-data "assets;assets" ^
    --add-data "config.server.example.json;." ^
    --hidden-import "faster_whisper" ^
    --hidden-import "ctranslate2" ^
    --hidden-import "vosk" ^
    --collect-all "vosk" ^
    --collect-all "faster_whisper" ^
    --collect-all "ctranslate2" ^
    stt\server_app.py

if errorlevel 1 (
    echo [ERROR] Server build FAILED
    pause
    exit /b 1
)

copy /y "dist\Clerkonator-Server.exe" "release\Clerkonator-Server.exe"
echo [OK] Server: release\Clerkonator-Server.exe

echo.
echo ════════════════════════════════════════════
echo  BUILD COMPLETE
echo ════════════════════════════════════════════
echo.
echo  release\Clerkonator-Client.exe
echo  release\Clerkonator-Server.exe
echo.
echo  NOTE: Models are NOT bundled in .exe.
echo  Place models/ folder next to .exe or configure paths in config.
echo.

REM Cleanup PyInstaller temp
if exist build rmdir /s /q build
if exist "Clerkonator-Client.spec" del /q "Clerkonator-Client.spec"
if exist "Clerkonator-Server.spec" del /q "Clerkonator-Server.spec"

pause
