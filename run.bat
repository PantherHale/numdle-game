@echo off
echo Installing dependencies...
py -3.11 -m pip install flask --quiet
echo.
echo =====================================================
echo  Numdle server
echo  Game:        http://localhost:5050
echo  Your logs:   gameapp\logs\
echo  Admin panel: http://localhost:5050/admin/logs
echo =====================================================
echo.
echo  Game logs are saved to the logs\ folder on THIS machine.
echo  Players cannot see or download them.
echo.
echo  When you want to train the AI:
echo    py -3.11 train_on_logs.py logs\week_YYYY-MM-DD.json
echo    py -3.11 precompute.py --next-week
echo.
echo Press Ctrl+C to stop the server.
echo.
py -3.11 app.py
pause
