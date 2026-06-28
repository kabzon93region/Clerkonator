@echo off
REM Активация venv StT (после cd в корень или из scripts\).
REM   call "%~dp0_stt_venv.cmd"
cd /d "%~dp0.."
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] venv не найден: %CD%\venv
    echo [INFO] scripts\setup.cmd
    exit /b 1
)

if exist "venv\_base_python\tcl\tcl8.6" (
    set "TCL_LIBRARY=%CD%\venv\_base_python\tcl\tcl8.6"
    set "TK_LIBRARY=%CD%\venv\_base_python\tcl\tk8.6"
)

call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Не удалось активировать venv
    exit /b 1
)
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python из venv недоступен после активации
    echo [INFO] scripts\setup.cmd --recreate
    exit /b 1
)
exit /b 0
