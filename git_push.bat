@echo off
setlocal

:: Set your GitHub repo URL
set REPO_URL=https://github.com/manulapulga/gwd_monthly_monitoring.git

:: Use main branch
set BRANCH=main

:: Initialize git if not already done
if not exist ".git" (
    echo Initializing new Git repo...
    git init
    git remote add origin %REPO_URL%
)

:: Add all files
git add .

:: Commit with timestamp
git commit -m "Auto commit %date% %time%"

:: Push to GitHub
git push -u origin %BRANCH%

echo.
echo Done!
pause
