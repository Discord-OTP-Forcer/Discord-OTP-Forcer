@echo off

set program_saved=0
set account_saved=0

for %%A in ("%~dp0..\..\config\program.yml") do set program_timestamp=%%~tA
for %%A in ("%~dp0..\..\config\account.yml") do set account_timestamp=%%~tA


echo Attempting to install dependencies...

where python >nul 2>&1
if not errorlevel 1 (
    python.exe -m pip install -r "%~dp0..\..\dependencies.txt"
    if errorlevel 1 (
        echo Failed to install dependencies...
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
echo From there, click on the 'Latest Python 3 Release' link
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
"%foundPython%" -m pip install -r "%~dp0..\..\dependencies.txt"
if errorlevel 1 (
    echo Pip install failed!
    pause
    exit /b 1
)
goto :success

:success
echo Dependencies installed successfully!

echo Set the program settings (program.yml) and your account details (account.yml) in the Notepad windows that have just opened
timeout /t 1 >nul
start notepad.exe "%~dp0..\..\config\program.yml"
start notepad.exe "%~dp0..\..\config\account.yml"

:LOOP
for %%A in ("%~dp0..\..\config\program.yml") do set current_program_timestamp=%%~tA
for %%A in ("%~dp0..\..\config\account.yml") do set current_account_timestamp=%%~tA

if not "%current_program_timestamp%"=="%program_timestamp%" set program_saved=1
if not "%current_account_timestamp%"=="%account_timestamp%" set account_saved=1

if "%program_saved%"=="1" if "%account_saved%"=="1" (
  echo Configuration files saved.
  choice /m "Start forcer session now?"

  if errorlevel 2 goto END
  if errorlevel 1 (
    start start.cmd
    exit
  )
)

timeout /t 1 >nul
goto LOOP

:END
echo -----------
echo Closing...
timeout /t 2 >nul
exit