@echo off

echo Uninstalling dependencies...

where python >nul 2>&1
if not errorlevel 1 (
    python.exe -m pip uninstall -r "%~dp0..\..\dependencies.txt" -y
    if errorlevel 1 (
        echo Failed to uninstall dependencies.
        pause
        exit /b 1
    )
    goto :success
)

echo Python not found in environment variables, checking explicitly...

set "foundPython="

for /d %%D in ("%LocalAppData%\Programs\Python\Python*") do (
    if exist "%%D\python.exe" (
        set "foundPython=%%D\python.exe"
        goto :runPython
    )
)

for /d %%D in ("%ProgramFiles%\Python*") do (
    if exist "%%D\python.exe" (
        set "foundPython=%%D\python.exe"
        goto :runPython
    )
)

echo Failed to find a Python installation. Make sure Python is installed in Local AppData or Program Files
echo If you don't have it, you can download Python from https://www.python.org/downloads/windows/
echo From there, click the 'Latest Python 3 Release' link
choice /m "Would you like to open your browser to download it?"
  if errorlevel 2 goto failureEnd
  if errorlevel 1 (
    echo Opening default browser
    start "" https://www.python.org/downloads/windows/
    exit
  )

:failureEnd
echo Closing...
timeout /t 2 >nul
exit /b 1

:runPython
"%foundPython%" -m pip uninstall -r "%~dp0..\..\dependencies.txt" -y
if errorlevel 1 (
    echo Failed to uninstall dependencies.
    pause
    exit /b 1
)
goto :success


:success
echo Dependencies uninstalled successfully!

pause
