@echo off
cd /d C:\Users\dexah69\Desktop\dice-destiny-bot
git add -A
git diff --cached --quiet
if %errorlevel% neq 0 (
    git commit -m "Auto-backup %date% %time%"
    git push origin HEAD
)
