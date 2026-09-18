@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem ============================================================
rem Local Python launcher and one-time environment installer.
rem Keep this file next to generate.bat, generate.py and codes.txt.
rem The original files are not modified.
rem ============================================================

set "ROOT=%~dp0"
set "ENV_DIR=%ROOT%.barcode_env"
set "ENV_PY=%ENV_DIR%\Scripts\python.exe"
set "SETUP_ONLY=0"
if "%~1"=="" set "SETUP_ONLY=1"

rem Use the prepared private environment when it is healthy.
if exist "%ENV_PY%" (
    "%ENV_PY%" -c "from PIL import Image, _imaging; from reportlab.graphics import renderPDF; from reportlab.graphics.barcode import eanbc; from reportlab.graphics.shapes import Drawing" >nul 2>&1
    if not errorlevel 1 goto :RUN
)

call :SETUP
if errorlevel 1 goto :FAIL

:RUN
if "%SETUP_ONLY%"=="1" goto :READY
"%ENV_PY%" %*
set "RC=%ERRORLEVEL%"
exit /b %RC%

:READY
echo.
echo ============================================================
echo   BARCODE ENVIRONMENT IS READY
echo ============================================================
echo Folder: "%ROOT%"
echo.
echo The original files were not modified:
echo   generate.bat
echo   generate.py
echo   codes.txt
echo.
echo Now run generate.bat as before.
echo This folder may be moved to another disk or directory.
echo ============================================================
echo.
pause
exit /b 0

:SETUP
cls
echo ============================================================
echo   PREPARING LOCAL BARCODE ENVIRONMENT
echo ============================================================
echo Folder: "%ROOT%"
echo.
echo The original files will not be modified.
echo.

if not exist "%ROOT%generate.bat" (
    echo ERROR: generate.bat was not found next to python.bat.
    exit /b 1
)
if not exist "%ROOT%generate.py" (
    echo ERROR: generate.py was not found next to python.bat.
    exit /b 1
)
if not exist "%ROOT%codes.txt" (
    echo ERROR: codes.txt was not found next to python.bat.
    exit /b 1
)

echo [1/4] Looking for standard Python 3.13...
call :FIND_BASE_PYTHON
if not defined BASE_MODE (
    echo Standard Python 3.13 was not found.
    echo Installing it for the current Windows user...
    call :INSTALL_PYTHON
    if errorlevel 1 exit /b 1
    call :FIND_BASE_PYTHON
)
if not defined BASE_MODE (
    echo ERROR: Standard Python 3.13 could not be prepared.
    exit /b 1
)
echo Standard Python 3.13 is ready.
echo.

echo [2/4] Creating a private environment...
if exist "%ENV_DIR%" rd /s /q "%ENV_DIR%" >nul 2>&1
if exist "%ENV_DIR%" (
    echo ERROR: The old .barcode_env folder could not be removed.
    echo Close programs using it and run again.
    exit /b 1
)

if /i "%BASE_MODE%"=="LAUNCHER" (
    py -3.13 -m venv "%ENV_DIR%"
) else (
    "%BASE_PY%" -m venv "%ENV_DIR%"
)
if errorlevel 1 (
    echo ERROR: The private environment could not be created.
    exit /b 1
)
if not exist "%ENV_PY%" (
    echo ERROR: The private Python executable was not created.
    exit /b 1
)
echo Private environment created.
echo.

echo [3/4] Installing Pillow and ReportLab...
"%ENV_PY%" -m pip install --disable-pip-version-check --no-input Pillow reportlab
if errorlevel 1 (
    echo ERROR: Pillow or ReportLab could not be installed.
    echo Check the Internet connection and run again.
    exit /b 1
)
echo Required libraries installed.
echo.

echo [4/4] Testing the complete generator environment...
"%ENV_PY%" -c "from PIL import Image, _imaging; from reportlab.graphics import renderPDF; from reportlab.graphics.barcode import eanbc; from reportlab.graphics.shapes import Drawing; print('Environment test passed.')"
if errorlevel 1 (
    echo ERROR: The environment test failed.
    exit /b 1
)

"%ENV_PY%" -m py_compile "%ROOT%generate.py"
if errorlevel 1 (
    echo ERROR: generate.py contains a syntax error.
    exit /b 1
)
if exist "%ROOT%__pycache__" rd /s /q "%ROOT%__pycache__" >nul 2>&1

echo.
echo Setup completed successfully.
exit /b 0

:FIND_BASE_PYTHON
set "BASE_MODE="
set "BASE_PY="

py -3.13 -c "import sys, sysconfig; raise SystemExit(0 if sys.version_info[:2] == (3,13) and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)" >nul 2>&1
if not errorlevel 1 (
    set "BASE_MODE=LAUNCHER"
    exit /b 0
)

if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
    "%LocalAppData%\Programs\Python\Python313\python.exe" -c "import sys, sysconfig; raise SystemExit(0 if sys.version_info[:2] == (3,13) and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "BASE_MODE=EXE"
        set "BASE_PY=%LocalAppData%\Programs\Python\Python313\python.exe"
        exit /b 0
    )
)

if exist "%ProgramFiles%\Python313\python.exe" (
    "%ProgramFiles%\Python313\python.exe" -c "import sys, sysconfig; raise SystemExit(0 if sys.version_info[:2] == (3,13) and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "BASE_MODE=EXE"
        set "BASE_PY=%ProgramFiles%\Python313\python.exe"
        exit /b 0
    )
)

exit /b 0

:INSTALL_PYTHON
where winget.exe >nul 2>&1
if not errorlevel 1 (
    winget install --id Python.Python.3.13 -e --scope user --accept-package-agreements --accept-source-agreements --silent
    if not errorlevel 1 exit /b 0
    echo WinGet installation failed. Trying the official installer...
)

set "PY_VERSION=3.13.14"
set "PY_INSTALLER=%TEMP%\python-3.13.14-installer.exe"
set "ARCH=%PROCESSOR_ARCHITECTURE%"
if defined PROCESSOR_ARCHITEW6432 set "ARCH=%PROCESSOR_ARCHITEW6432%"

if /i "%ARCH%"=="ARM64" (
    set "PY_URL=https://www.python.org/ftp/python/3.13.14/python-3.13.14-arm64.exe"
    set "PY_SHA=3090f98038f332ceeca0ba40d77b7a4d94a4a25b7107e6cf341547e91d983f18"
) else if /i "%ARCH%"=="x86" (
    set "PY_URL=https://www.python.org/ftp/python/3.13.14/python-3.13.14.exe"
    set "PY_SHA=012f050539353e6521ac7976a6b63e232102977e1dfcc747ca7fb743357ae8d1"
) else (
    set "PY_URL=https://www.python.org/ftp/python/3.13.14/python-3.13.14-amd64.exe"
    set "PY_SHA=c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0"
)

echo Downloading the official Python installer...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Uri $env:PY_URL -OutFile $env:PY_INSTALLER; $h=(Get-FileHash -Algorithm SHA256 $env:PY_INSTALLER).Hash.ToLowerInvariant(); if($h -ne $env:PY_SHA.ToLowerInvariant()){Write-Host 'ERROR: Installer checksum mismatch.'; exit 2}" 
if errorlevel 1 (
    if exist "%PY_INSTALLER%" del /q "%PY_INSTALLER%" >nul 2>&1
    echo ERROR: The official Python installer could not be downloaded or verified.
    exit /b 1
)

echo Installing standard Python 3.13...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 Include_pip=1 Include_test=0 Include_doc=0 Shortcuts=0 SimpleInstall=1
set "INSTALL_RC=%ERRORLEVEL%"
del /q "%PY_INSTALLER%" >nul 2>&1
if not "%INSTALL_RC%"=="0" (
    echo ERROR: Python installer returned code %INSTALL_RC%.
    exit /b 1
)
exit /b 0

:FAIL
echo.
echo Installation was not completed. Read the message above.
echo.
pause
exit /b 1
