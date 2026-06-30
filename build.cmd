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

REM Use venv Python for building (packages are installed there)
set "PYTHON=venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] venv not found. Run setup.cmd first.
    pause
    exit /b 1
)

REM Check PyInstaller in venv
"%PYTHON%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [INFO] Installing PyInstaller in venv...
    "%PYTHON%" -m pip install pyinstaller
)

REM Ensure icons exist
"%PYTHON%" -c "from utils.app_icon import ensure_icon_files, ensure_server_icon_files; ensure_icon_files(); ensure_server_icon_files()"
set CLIENT_ICON=assets\app_icon.ico
set SERVER_ICON=assets\server_icon.ico

REM Create release directory
if not exist release mkdir release

echo.
echo ════════════════════════════════════════════
echo  Building CLIENT...
echo ════════════════════════════════════════════
echo.

"%PYTHON%" -m PyInstaller --noconfirm --onefile --windowed ^
    --name "Clerkonator-Client" ^
    --icon "%CLIENT_ICON%" ^
    --add-data "assets;assets" ^
    --add-data "config.client.example.json;." ^
    --hidden-import "pynput.keyboard._win32" ^
    --hidden-import "pynput.mouse._win32" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "pygame" ^
    --hidden-import "vosk" ^
    --hidden-import "pyaudio" ^
    --hidden-import "pyperclip" ^
    --hidden-import "pystray" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL.Image" ^
    --hidden-import "certifi" ^
    --hidden-import "httpx" ^
    --hidden-import "faster_whisper" ^
    --hidden-import "ctranslate2" ^
    --hidden-import "onnxruntime" ^
    --hidden-import "huggingface_hub" ^
    --collect-all "vosk" ^
    --collect-all "PIL" ^
    --collect-all "pystray" ^
    --collect-all "certifi" ^
    --collect-all "httpx" ^
    --collect-all "faster_whisper" ^
    --collect-all "ctranslate2" ^
    --collect-all "onnxruntime" ^
    --collect-all "huggingface_hub" ^
    --collect-all "nvidia-cublas-cu12" ^
    --collect-all "nvidia-cudnn-cu12" ^
    --collect-all "nvidia-cuda-runtime-cu12" ^
    --collect-all "nvidia-cuda-nvrtc-cu12" ^
    --add-binary "venv\Lib\site-packages\nvidia\cublas\bin\cublas64_12.dll;nvidia\cublas\bin" ^
    --add-binary "venv\Lib\site-packages\nvidia\cublas\bin\cublasLt64_12.dll;nvidia\cublas\bin" ^
    --add-binary "venv\Lib\site-packages\nvidia\cudnn\bin\cudnn64_9.dll;nvidia\cudnn\bin" ^
    --add-binary "venv\Lib\site-packages\nvidia\cuda_runtime\bin\cudart64_12.dll;nvidia\cuda_runtime\bin" ^
    --add-binary "venv\Lib\site-packages\nvidia\cuda_nvrtc\bin\nvrtc64_120_0.dll;nvidia\cuda_nvrtc\bin" ^
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

REM Clean build cache to ensure fresh dependencies
if exist build rmdir /s /q build
if exist "Clerkonator-Server.spec" del /q "Clerkonator-Server.spec"

REM Server needs console window for show/hide via tray menu
"%PYTHON%" -m PyInstaller --clean --noconfirm --onefile ^
    --name "Clerkonator-Server" ^
    --icon "%SERVER_ICON%" ^
    --add-data "assets;assets" ^
    --add-data "config.server.example.json;." ^
    --hidden-import "faster_whisper" ^
    --hidden-import "ctranslate2" ^
    --hidden-import "vosk" ^
    --hidden-import "pystray" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL.Image" ^
    --hidden-import "PIL.ImageDraw" ^
    --hidden-import "huggingface_hub" ^
    --hidden-import "httpx" ^
    --collect-all "vosk" ^
    --collect-all "faster_whisper" ^
    --collect-all "ctranslate2" ^
    --collect-all "huggingface_hub" ^
    --collect-all "pystray" ^
    --collect-all "PIL" ^
    --collect-all "nvidia-cublas-cu12" ^
    --collect-all "nvidia-cudnn-cu12" ^
    --collect-all "nvidia-cuda-runtime-cu12" ^
    --collect-all "nvidia-cuda-nvrtc-cu12" ^
    --add-binary "venv\Lib\site-packages\nvidia\cublas\bin\cublas64_12.dll;nvidia\cublas\bin" ^
    --add-binary "venv\Lib\site-packages\nvidia\cublas\bin\cublasLt64_12.dll;nvidia\cublas\bin" ^
    --add-binary "venv\Lib\site-packages\nvidia\cudnn\bin\cudnn64_9.dll;nvidia\cudnn\bin" ^
    --add-binary "venv\Lib\site-packages\nvidia\cuda_runtime\bin\cudart64_12.dll;nvidia\cuda_runtime\bin" ^
    --add-binary "venv\Lib\site-packages\nvidia\cuda_nvrtc\bin\nvrtc64_120_0.dll;nvidia\cuda_nvrtc\bin" ^
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
