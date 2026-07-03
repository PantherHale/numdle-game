@echo off
echo === Numdle Weekly Update ===
cd /d "%~dp0"

echo.
echo [1/3] Running precompute for next 2 weeks...
py -3.11 precompute.py --next-week --weeks 2
if errorlevel 1 (echo ERROR: precompute failed & pause & exit /b 1)

echo.
echo [2/3] Committing files...
git add logs/ai_game_log.json public/daily_data.json
git commit -m "weekly: precompute AI games for next 2 weeks"
if errorlevel 1 (echo Nothing new to commit, skipping...)

echo.
echo [3/3] Pushing to GitHub...
git push
if errorlevel 1 (echo ERROR: git push failed & pause & exit /b 1)

echo.
echo === Done! ===
echo Cloudflare will auto-deploy in ~1 minute.
echo PythonAnywhere will auto-pull tonight (if scheduled task is set up).
echo.
pause
