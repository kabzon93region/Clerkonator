@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
REM ============================================
REM Clerkonator — Publish to GitHub via gh CLI
REM Usage: publish.cmd [commit message]
REM ============================================

cd /d "%~dp0"

REM Disable git pager to avoid interactive less/more
set "GIT_PAGER=cat"
set "GIT_TERMINAL_PROMPT=0"

echo [PUBLISH] Clerkonator — Git + GitHub
echo.

REM Check gh CLI
where gh >nul 2>&1
if errorlevel 1 (
    echo [ERROR] gh CLI not found. Install: https://cli.github.com/
    pause
    exit /b 1
)

REM Check git
where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] git not found.
    pause
    exit /b 1
)

REM Check if git repo exists
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    echo [INFO] Initializing git repository...
    git init
    git branch -M main
)

REM Get commit message (auto-generate if not provided)
set "MSG=%~1"
if "!MSG!"=="" (
    for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm'"') do set "MSG=update %%T"
)
if "!MSG!"=="" set "MSG=update"

REM Stage all changes
echo [STEP] Staging changes...
git add -A

REM Check if there are changes to commit
git --no-pager diff --cached --quiet
if %errorlevel%==0 (
    echo [INFO] Nothing to commit — working tree is clean.
    pause
    exit /b 0
)

REM Show what will be committed
echo.
echo [INFO] Changes to commit:
git --no-pager diff --cached --stat
echo.

REM Commit
echo [STEP] Committing...
git commit -m "%MSG%"
if errorlevel 1 (
    echo [ERROR] Commit failed.
    pause
    exit /b 1
)

REM Check if remote exists (hardcoded repo)
set "REPO=kabzon93region/Clerkonator"
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo [INFO] No remote configured. Setting up origin...
    git remote add origin https://github.com/%REPO%.git
    echo [STEP] Creating GitHub repository...
    gh repo create "%REPO%" --public --source=. --push
    if errorlevel 1 (
        echo [ERROR] Failed to create repository.
        echo [INFO] Try manually: gh repo create %REPO%
        pause
        exit /b 1
    )
    echo [OK] Repository created and pushed!
) else (
    echo [STEP] Pulling remote changes...
    git pull --rebase
    if errorlevel 1 (
        echo [WARN] Pull failed. Trying push anyway...
    )
    echo [STEP] Pushing to origin...
    git push
    if errorlevel 1 (
        echo [WARN] Push failed. Trying with --set-upstream...
        for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
        git push --set-upstream origin "!BRANCH!"
        if errorlevel 1 (
            echo [ERROR] Push failed.
            pause
            exit /b 1
        )
    )
    echo [OK] Pushed to GitHub!
)

echo.
echo [DONE] Published successfully.
echo.
pause
