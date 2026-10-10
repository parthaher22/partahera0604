@echo off
setlocal
set base=C:\Users\PARTH\OneDrive\Desktop\E-grampanchyat\backend
set python=%base%\.venv\Scripts\python.exe
set pidfile=%base%\uvicorn.pid

if not exist "%python%" (
  echo VENV PYTHON NOT FOUND: %python%
  pause
  exit /b 1
)

:: Stop any previous instance to free port 5000 before starting fresh.
if exist "%pidfile%" (
  set /p oldpid=<"%pidfile%"
  taskkill /F /PID %oldpid% /T >nul 2>&1
  timeout /t 1 /nobreak >nul
)
taskkill /F /IM "python.exe" /FI "WINDOWTITLE eq gramsetu-uvicorn*" >nul 2>&1

start "gramsetu-uvicorn" /MIN /D "%base%" "%python%" -m uvicorn app.main:app --host 127.0.0.1 --port 5000

:: Wait for uvicorn then record its PID by window title.
timeout /t 3 /nobreak >nul
for /f "tokens=2" %%p in ('tasklist /FI "WINDOWTITLE eq gramsetu-uvicorn*" /FO LIST ^| findstr /R /C:"PID:"') do set pid=%%p
if not defined pid (
  echo COULD NOT FIND SERVER PROCESS. Check that uvicorn installed.
  pause
  exit /b 1
)
> "%pidfile%" echo %pid%
echo started (PID %pid%) on http://127.0.0.1:5000
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5000/docs"
endlocal