@echo off
setlocal

set "RELEASE_DIR=%~dp0"
set "APP_ROOT=%RELEASE_DIR%..\.."
set "PYTHONPATH=%APP_ROOT%\src;%PYTHONPATH%"

if not exist "%APP_ROOT%\src\cm_test_chamber\cli.py" (
    echo Could not find Cognition Mesh Test Chamber source files:
    echo "%APP_ROOT%\src\cm_test_chamber\cli.py"
    echo.
    echo Make sure this file is still inside release\windows in the cognition-mesh-test-chamber repo.
    pause
    exit /b 1
)

cd /d "%APP_ROOT%"

echo Starting Cognition Mesh Test Chamber dashboard...
echo.
python -m cm_test_chamber.cli dashboard --host 127.0.0.1 --port 8765 %*

if errorlevel 1 (
    echo.
    echo Cognition Mesh Test Chamber stopped with an error.
    pause
)
