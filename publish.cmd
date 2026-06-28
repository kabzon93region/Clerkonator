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

REM Get commit message
set "MSG=%~1"
if "%MSG%"=="" (
    set /p "MSG=Commit message: "
)
if "%MSG%"=="" (
    echo [ERROR] Commit message is required.
    pause
    exit /b 1
)

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

REM Check if remote exists
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo.
    echo [INFO] No remote 'origin' configured.
    set /p "REPO=Enter GitHub repo (e.g. user/repo): "
    if "!REPO!"=="" (
        echo [ERROR] Repository is required.
        pause
        exit /b 1
    )
    echo [STEP] Creating GitHub repository...
    gh repo create "!REPO!" --public --source=. --push
    if errorlevel 1 (
        echo [ERROR] Failed to create repository.
        echo [INFO] Try manually: gh repo create
        pause
        exit /b 1
    )
    echo [OK] Repository created and pushed!
) else (
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
