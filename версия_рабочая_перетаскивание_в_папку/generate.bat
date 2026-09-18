@echo off
chcp 65001 >nul
title Запуск generate.py

:: Переход в папку, где находится сам батник (даже если это UNC)
pushd "%~dp0"

echo Текущая папка: %CD%
echo Запуск generate.py...

:: Если Python не добавлен в PATH, укажите полный путь к python.exe, например:
:: "C:\Users\ВашеИмя\AppData\Local\Programs\Python\Python311\python.exe" generate.py
python generate.py

if errorlevel 1 (
    echo Ошибка при выполнении скрипта.
) else (
    echo Скрипт завершён успешно.
)

:: Возврат к исходной папке
popd

pause