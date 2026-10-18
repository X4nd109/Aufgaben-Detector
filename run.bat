@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Aufgaben-Detector

cls

REM -----------------------------------------------------------------
REM Python-Interpreter finden
REM -----------------------------------------------------------------
set "PYTHON_EXE="

if defined LOCALAPPDATA (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
)

if not defined PYTHON_EXE if exist "C:\Python312\python.exe" set "PYTHON_EXE=C:\Python312\python.exe"
if not defined PYTHON_EXE if exist "C:\Python310\python.exe" set "PYTHON_EXE=C:\Python310\python.exe"

REM System-Python pruefen (WindowsApps ausschliessen)
if not defined PYTHON_EXE (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        if not defined PYTHON_EXE (
            echo %%i | findstr /i "WindowsApps" >nul 2>nul
            if errorlevel 1 set "PYTHON_EXE=%%i"
        )
    )
)

if not defined PYTHON_EXE (
    py -3 --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_EXE=py -3"
)

REM Falls Python nirgends gefunden wurde:
if not defined PYTHON_EXE (
    echo.
    echo =======================================================
    echo  [!] Python wurde auf diesem Computer nicht gefunden!
    echo =======================================================
    echo.
    echo  Der Aufgaben-Detector benoetigt Python.
    echo.
    set /p "RUN_SETUP=Moechtest du das Setup jetzt starten? (J/N): "
    if /i "!RUN_SETUP!"=="J" (
        call "%~dp0setup.bat"
        exit /b 0
    )
    pause
    exit /b 9009
)

REM Programm ausfuehren
"%PYTHON_EXE%" "%~dp0main.py" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Programm beendet mit Fehlercode %ERRORLEVEL%
    pause
)
