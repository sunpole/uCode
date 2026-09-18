@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title Генератор штрихкодов EAN-13 — размер 220x100 pt

rem Убираем внешние переменные, способные повредить локальную среду Python.
set "PYTHONHOME="
set "PYTHONPATH="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_NO_INPUT=1"

pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ОШИБКА: не удалось открыть папку BAT-файла.
    echo Переместите BAT-файл в обычную локальную папку и запустите снова.
    echo.
    pause
    exit /b 1
)

set "ROOT=%CD%"
set "SCRIPT=%ROOT%\generate.py"
set "CODES=%ROOT%\codes.txt"
set "OUTPUT=%ROOT%\barcodes"
set "VENV=%ROOT%\.barcode_env"
set "VENV_PY=%VENV%\Scripts\python.exe"
set "BASE_MODE="
set "BASE_VERSION="
set "BASE_EXE="
set "PY_VERSION=3.13.14"
set "PY_INSTALLER=%TEMP%\python-%PY_VERSION%-barcode-setup.exe"


echo ============================================================
echo   ГЕНЕРАТОР EAN-13 — ТОЧНЫЙ РАЗМЕР 220 x 100 pt
echo ============================================================
echo Папка программы: "%ROOT%"
echo.


echo [1/7] Проверка Python...
call :find_base_python
if errorlevel 1 (
    echo Python не найден. Устанавливаю Python 3.13...
    call :install_python_313
    if errorlevel 1 goto :python_install_failed
    call :find_base_python
    if errorlevel 1 goto :python_not_found_after_install
)
call :show_base_version
if errorlevel 1 goto :python_not_found_after_install
echo Базовый Python готов.
echo.


echo [2/7] Проверка отдельной среды программы...
call :ensure_runtime
if errorlevel 1 (
    echo.
    echo Текущий Python не смог подготовить рабочую среду.
    echo Устанавливаю стабильный Python 3.13 и повторяю настройку...

    call :run_base -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,13) else 1)" >nul 2>&1
    if not errorlevel 1 goto :runtime_failed

    call :install_python_313
    if errorlevel 1 goto :python_install_failed
    call :find_base_python
    if errorlevel 1 goto :python_not_found_after_install

    if exist "%VENV%" rmdir /s /q "%VENV%" >nul 2>&1
    call :ensure_runtime
    if errorlevel 1 goto :runtime_failed
)
echo Локальная среда готова.
echo.


echo [3/7] Проверка Pillow и reportlab...
call :test_runtime
if errorlevel 1 goto :runtime_failed
for /f "delims=" %%V in ('"%VENV_PY%" -c "import PIL, reportlab; print('Pillow ' + PIL.__version__ + ', reportlab ' + reportlab.Version)"') do echo %%V
echo Библиотеки действительно загружаются.
echo.


echo [4/7] Проверка generate.py и точного размера 220 x 100 pt...
if not exist "%SCRIPT%" (
    echo Скрипт отсутствует. Создаю generate.py с исходным размером...
    call :write_python_script
    if errorlevel 1 goto :script_create_failed
) else (
    findstr /b /c:"# BARCODE_GENERATOR_AUTOMANAGED_V3_EXACT_220X100" "%SCRIPT%" >nul 2>&1
    if not errorlevel 1 (
        "%VENV_PY%" -m py_compile "%SCRIPT%" >nul 2>&1
        if errorlevel 1 (
            echo Автоматический generate.py повреждён. Восстанавливаю...
            copy /y "%SCRIPT%" "%SCRIPT%.broken.bak" >nul 2>&1
            call :write_python_script
            if errorlevel 1 goto :script_create_failed
        )
    ) else (
        findstr /b /c:"# BARCODE_GENERATOR_AUTOMANAGED_V2" "%SCRIPT%" >nul 2>&1
        if not errorlevel 1 (
            echo Обновляю созданную ранее версию и возвращаю исходный размер...
            copy /y "%SCRIPT%" "%SCRIPT%.v2.backup" >nul 2>&1
            call :write_python_script
            if errorlevel 1 goto :script_create_failed
        ) else (
            "%VENV_PY%" -m py_compile "%SCRIPT%" >nul 2>&1
            if errorlevel 1 (
                echo Пользовательский generate.py повреждён. Сохраняю копию и восстанавливаю...
                copy /y "%SCRIPT%" "%SCRIPT%.broken.bak" >nul 2>&1
                call :write_python_script
                if errorlevel 1 goto :script_create_failed
            ) else (
                echo Найден пользовательский generate.py — BAT его не изменяет.
            )
        )
    )
)
echo generate.py готов.
echo Требуемый размер PDF: 220 x 100 pt ^(77,61 x 35,28 мм^).
echo.


echo [5/7] Проверка codes.txt...
if not exist "%CODES%" (
    type nul > "%CODES%"
    echo Создан пустой файл codes.txt.
)

for %%A in ("%CODES%") do if %%~zA EQU 0 goto :edit_codes
findstr /r "[0-9]" "%CODES%" >nul 2>&1
if errorlevel 1 goto :edit_codes
goto :codes_ready

:edit_codes
echo.
echo В codes.txt пока нет кодов.
echo Сейчас откроется Блокнот.
echo Введите по одному коду в каждой строке, сохраните файл
echo и закройте Блокнот. Допустимы коды из 12 или 13 цифр.
echo.
start "" /wait notepad.exe "%CODES%"

for %%A in ("%CODES%") do if %%~zA EQU 0 goto :no_codes
findstr /r "[0-9]" "%CODES%" >nul 2>&1
if errorlevel 1 goto :no_codes

:codes_ready
if not exist "%OUTPUT%" mkdir "%OUTPUT%" >nul 2>&1
if errorlevel 1 goto :output_create_failed
echo codes.txt готов.
echo.


echo [6/7] Контрольный импорт перед запуском...
call :test_runtime
if errorlevel 1 (
    echo Среда неожиданно перестала работать. Выполняю одно восстановление...
    if exist "%VENV%" rmdir /s /q "%VENV%" >nul 2>&1
    call :ensure_runtime
    if errorlevel 1 goto :runtime_failed
)
echo Контрольный импорт успешен.
echo.


echo [7/7] Создание PDF-файлов...
"%VENV_PY%" "%SCRIPT%"
set "GEN_EXIT=%ERRORLEVEL%"

if "%GEN_EXIT%"=="0" goto :success
if "%GEN_EXIT%"=="2" goto :no_valid_codes
goto :generation_failed


:success
echo.
echo ============================================================
echo   ГОТОВО: PDF 220 x 100 pt созданы в папке barcodes
echo ============================================================
start "" "%OUTPUT%"
goto :finish_ok

:no_codes
echo.
echo Коды не введены. Ничего не создавалось.
echo Запустите BAT снова после заполнения codes.txt.
goto :finish_error

:no_valid_codes
echo.
echo Не найдено ни одного корректного кода.
echo Проверьте сообщения выше и исправьте codes.txt.
start "" notepad.exe "%CODES%"
goto :finish_error

:python_install_failed
echo.
echo ОШИБКА: Python 3.13 не удалось установить автоматически.
echo Проверьте интернет, антивирус и права текущего пользователя.
goto :finish_error

:python_not_found_after_install
echo.
echo ОШИБКА: установка завершилась, но рабочий Python не найден.
echo Перезагрузите Windows и запустите BAT ещё раз.
goto :finish_error

:runtime_failed
echo.
echo ОШИБКА: не удалось создать рабочую среду программы.
echo Возможные причины: нет интернета, установка блокируется антивирусом,
echo прокси-сервером или отсутствует право записи в папку программы.
echo Системные пакеты Python не изменялись.
goto :finish_error

:script_create_failed
echo.
echo ОШИБКА: не удалось создать generate.py рядом с BAT-файлом.
echo Проверьте право записи в папку "%ROOT%".
goto :finish_error

:output_create_failed
echo.
echo ОШИБКА: не удалось создать папку barcodes.
echo Проверьте право записи в папку "%ROOT%".
goto :finish_error

:generation_failed
echo.
echo ОШИБКА: generate.py завершился с кодом %GEN_EXIT%.
echo Посмотрите сообщения выше.
goto :finish_error

:finish_ok
echo.
echo Для повторной генерации измените codes.txt и снова запустите BAT.
echo Служебная папка .barcode_env должна оставаться рядом с BAT-файлом.
echo.
pause
popd
exit /b 0

:finish_error
echo.
pause
popd
exit /b 1


:find_base_python
set "BASE_MODE="
set "BASE_VERSION="
set "BASE_EXE="

rem Сначала предпочитаем стабильную ветку 3.13, затем уже установленную 3.14.
for %%V in (3.13 3.14 3.12 3.11 3.10) do (
    py -%%V -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "BASE_MODE=PY"
        set "BASE_VERSION=%%V"
        exit /b 0
    )
)

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%ProgramFiles%\Python313\python.exe"
    "%ProgramFiles%\Python314\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "%ProgramFiles%\Python311\python.exe"
) do (
    call :test_python_path "%%~P"
    if not errorlevel 1 exit /b 0
)

for /f "delims=" %%P in ('where python.exe 2^>nul') do (
    call :test_python_path "%%P"
    if not errorlevel 1 exit /b 0
)

exit /b 1


:test_python_path
if not exist "%~1" exit /b 1
echo(%~1| findstr /i /c:"\WindowsApps\" >nul 2>&1
if not errorlevel 1 exit /b 1
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
set "BASE_MODE=EXE"
set "BASE_EXE=%~1"
exit /b 0


:show_base_version
call :run_base --version
exit /b %ERRORLEVEL%


:run_base
if /I "%BASE_MODE%"=="PY" goto :run_base_py
if /I "%BASE_MODE%"=="EXE" goto :run_base_exe
exit /b 1

:run_base_py
py -%BASE_VERSION% %*
exit /b %ERRORLEVEL%

:run_base_exe
"%BASE_EXE%" %*
exit /b %ERRORLEVEL%


:ensure_runtime
if exist "%VENV_PY%" (
    call :test_runtime
    if not errorlevel 1 exit /b 0
    echo Локальная среда повреждена или несовместима. Пересоздаю её...
    rmdir /s /q "%VENV%" >nul 2>&1
)

echo Создаю отдельную среду: .barcode_env
call :run_base -m venv "%VENV%"
if errorlevel 1 exit /b 1
if not exist "%VENV_PY%" exit /b 1

"%VENV_PY%" -m ensurepip --upgrade >nul 2>&1
if errorlevel 1 exit /b 1

"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b 1

echo Устанавливаю совместимые Pillow и reportlab...
"%VENV_PY%" -m pip install --upgrade --no-cache-dir --only-binary=:all: Pillow
if errorlevel 1 exit /b 1

"%VENV_PY%" -m pip install --upgrade --no-cache-dir reportlab
if errorlevel 1 exit /b 1

call :test_runtime
exit /b %ERRORLEVEL%


:test_runtime
if not exist "%VENV_PY%" exit /b 1
"%VENV_PY%" -c "from PIL import Image; from reportlab.graphics import renderPDF; from reportlab.graphics.barcode import eanbc; from reportlab.graphics.shapes import Drawing" >nul 2>&1
exit /b %ERRORLEVEL%


:install_python_313
py -3.13 -c "import sys" >nul 2>&1
if not errorlevel 1 exit /b 0
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" exit /b 0

where winget.exe >nul 2>&1
if errorlevel 1 goto :install_python_official

echo Установка Python 3.13 через Windows Package Manager...
winget install --id Python.Python.3.13 -e --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
if not errorlevel 1 (
    py -3.13 -c "import sys" >nul 2>&1
    if not errorlevel 1 exit /b 0
    if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" exit /b 0
)

echo WinGet не завершил установку. Использую официальный установщик Python.

:install_python_official
set "PY_FILE=python-%PY_VERSION%-amd64.exe"
if /I "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "PY_FILE=python-%PY_VERSION%-arm64.exe"
if /I "%PROCESSOR_ARCHITECTURE%"=="x86" if /I not "%PROCESSOR_ARCHITEW6432%"=="AMD64" set "PY_FILE=python-%PY_VERSION%.exe"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/%PY_FILE%"

echo Загрузка подписанного установщика с python.org...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri $env:PY_URL -OutFile $env:PY_INSTALLER"
if errorlevel 1 exit /b 1
if not exist "%PY_INSTALLER%" exit /b 1

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s=Get-AuthenticodeSignature -LiteralPath $env:PY_INSTALLER; if($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'Python Software Foundation'){ exit 1 }"
if errorlevel 1 (
    echo Цифровая подпись установщика не прошла проверку.
    del /q "%PY_INSTALLER%" >nul 2>&1
    exit /b 1
)

echo Установка Python только для текущего пользователя...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_pip=1 Include_test=0 Include_doc=0 Shortcuts=0
set "INSTALL_EXIT=%ERRORLEVEL%"
del /q "%PY_INSTALLER%" >nul 2>&1
if not "%INSTALL_EXIT%"=="0" exit /b 1

if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" exit /b 0
py -3.13 -c "import sys" >nul 2>&1
exit /b %ERRORLEVEL%


:write_python_script
set "TARGET_SCRIPT=%SCRIPT%"
set "PY_SCRIPT_B64=IyBCQVJDT0RFX0dFTkVSQVRPUl9BVVRPTUFOQUdFRF9WM19FWEFDVF8yMjBYMTAwCmltcG9ydCBvcwppbXBvcnQgc3lzCmZyb20gcmVwb3J0bGFiLmdyYXBoaWNzLmJhcmNvZGUgaW1wb3J0IGVhbmJjCmZyb20gcmVwb3J0bGFiLmdyYXBoaWNzLnNoYXBlcyBpbXBvcnQgRHJhd2luZwpmcm9tIHJlcG9ydGxhYi5ncmFwaGljcyBpbXBvcnQgcmVuZGVyUERGCgojINCi0L7Rh9C90YvQuSDRgNCw0LfQvNC10YAgUERGINC40Lcg0LjRgdGF0L7QtNC90L7Qs9C+INCz0LXQvdC10YDQsNGC0L7RgNCwLgpQREZfV0lEVEhfUFQgPSAyMjAKUERGX0hFSUdIVF9QVCA9IDEwMApQVF9UT19NTSA9IDI1LjQgLyA3MgoKc2NyaXB0X2RpciA9IG9zLnBhdGguZGlybmFtZShvcy5wYXRoLmFic3BhdGgoX19maWxlX18pKQpJTlBVVF9GSUxFID0gb3MucGF0aC5qb2luKHNjcmlwdF9kaXIsICJjb2Rlcy50eHQiKQpPVVRQVVRfRElSID0gb3MucGF0aC5qb2luKHNjcmlwdF9kaXIsICJiYXJjb2RlcyIpCgppZiBub3Qgb3MucGF0aC5pc2ZpbGUoSU5QVVRfRklMRSk6CiAgICBwcmludChmItCe0YjQuNCx0LrQsDog0YTQsNC50Lsge0lOUFVUX0ZJTEV9INC90LUg0L3QsNC50LTQtdC9ISIpCiAgICByYWlzZSBTeXN0ZW1FeGl0KDEpCgpvcy5tYWtlZGlycyhPVVRQVVRfRElSLCBleGlzdF9vaz1UcnVlKQoKd2l0aCBvcGVuKElOUFVUX0ZJTEUsICJyIiwgZW5jb2Rpbmc9InV0Zi04LXNpZyIpIGFzIGY6CiAgICBjb2RlcyA9IFtsaW5lLnN0cmlwKCkgZm9yIGxpbmUgaW4gZiBpZiBsaW5lLnN0cmlwKCldCgpwcmludChmItCd0LDQudC00LXQvdC+INC60L7QtNC+0LIg0LIg0YTQsNC50LvQtToge2xlbihjb2Rlcyl9IikKcHJpbnQoCiAgICAi0KDQsNC30LzQtdGAINC60LDQttC00L7Qs9C+IFBERjogIgogICAgZiJ7UERGX1dJRFRIX1BUfSB4IHtQREZfSEVJR0hUX1BUfSBwdCAiCiAgICBmIih7UERGX1dJRFRIX1BUICogUFRfVE9fTU06LjJmfSB4IHtQREZfSEVJR0hUX1BUICogUFRfVE9fTU06LjJmfSBtbSkiCikKCmlmIG5vdCBjb2RlczoKICAgIHByaW50KCLQktC90LjQvNCw0L3QuNC1OiDRhNCw0LnQuyDQv9GD0YHRgi4g0J3QuNGH0LXQs9C+INC90LUg0YHQvtC30LTQsNC90L4uIikKICAgIHJhaXNlIFN5c3RlbUV4aXQoMCkKCmNyZWF0ZWQgPSAwCmZvciBjb2RlIGluIGNvZGVzOgogICAgaWYgbGVuKGNvZGUpICE9IDEzIG9yIG5vdCBjb2RlLmlzZGlnaXQoKToKICAgICAgICBwcmludChmItCf0YDQvtC/0YPRidC10L0g0L3QtdCy0LXRgNC90YvQuSDQutC+0LQ6IHtjb2RlfSIpCiAgICAgICAgY29udGludWUKCiAgICAjINCh0L7RhdGA0LDQvdGP0LXQvCDQuNGB0YXQvtC00L3Rg9GOINC70L7Qs9C40LrRgyDQuCDQuNGB0YXQvtC00L3Ri9C5INC80LDRgdGI0YLQsNCxINCx0LXQtyDQuNC30LzQtdC90LXQvdC40LkuCiAgICBiYXJjb2RlID0gZWFuYmMuRWFuMTNCYXJjb2RlV2lkZ2V0KGNvZGUpCiAgICBkcmF3aW5nID0gRHJhd2luZyhQREZfV0lEVEhfUFQsIFBERl9IRUlHSFRfUFQpCiAgICBkcmF3aW5nLmFkZChiYXJjb2RlKQoKICAgIGZpbGVuYW1lID0gb3MucGF0aC5qb2luKE9VVFBVVF9ESVIsIGYie2NvZGV9LnBkZiIpCiAgICByZW5kZXJQREYuZHJhd1RvRmlsZShkcmF3aW5nLCBmaWxlbmFtZSkKICAgIHByaW50KGYi0KHQvtC30LTQsNC9OiB7ZmlsZW5hbWV9IikKICAgIGNyZWF0ZWQgKz0gMQoKcHJpbnQoZiLQk9C+0YLQvtCy0L4hINCh0L7Qt9C00LDQvdC+IFBERjoge2NyZWF0ZWR9IikKcmFpc2UgU3lzdGVtRXhpdCgwIGlmIGNyZWF0ZWQgZWxzZSAyKQo="
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[IO.File]::WriteAllBytes($env:TARGET_SCRIPT,[Convert]::FromBase64String($env:PY_SCRIPT_B64))"
if errorlevel 1 exit /b 1
if not exist "%SCRIPT%" exit /b 1
"%VENV_PY%" -m py_compile "%SCRIPT%" >nul 2>&1
exit /b %ERRORLEVEL%
