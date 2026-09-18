rem +--------------------------------------------------------------------------------------+
rem |                                     uCode_v_2.0                                      |
rem |    Copyright (c) 2026 Anton Magomedov | @sunpole | @xcve33 | All rights reserved.    |
rem +--------------------------------------------------------------------------------------+

@echo off
chcp 65001 >nul
title Запуск generate.py

rem Переход в папку, где находится сам BAT-файл
pushd "%~dp0"

echo Текущая папка: %CD%
echo Запуск generate.py...
echo.

rem Запуск через локальный python.bat
call "%~dp0python.bat" "%~dp0generate.py"
set "RESULT=%ERRORLEVEL%"

echo.
if not "%RESULT%"=="0" (
    echo Ошибка при выполнении скрипта. Код ошибки: %RESULT%
) else (
    echo Скрипт завершён успешно.
)

rem Возврат в исходную папку
popd

echo.
pause
exit /b %RESULT%