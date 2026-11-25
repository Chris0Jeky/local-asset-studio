@echo off
setlocal
cd /d "%~dp0..\..\..\.."
py -3 "%~dp0run.py" owner-start --prospective %*
set "P35_EXIT=%ERRORLEVEL%"
echo.
echo P35 has stopped. Read the result above before taking any further action.
echo An uncertain submission must be inspected with status; do not clear its journal or retry it.
pause
exit /b %P35_EXIT%
