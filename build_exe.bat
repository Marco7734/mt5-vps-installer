@echo off
REM build_exe.bat — Compila setup_mt5_vps.exe
REM Installa automaticamente Python e PyInstaller se mancanti

echo.
echo ============================================
echo  mt5-vps-installer -- Build VPS Installer
echo ============================================
echo.

REM -----------------------------------------------
REM STEP 1: Controlla se Python e' disponibile
REM -----------------------------------------------
echo [1/4] Verifica Python...
python --version >nul 2>&1
if not errorlevel 1 goto PYTHON_OK

echo  Python non trovato. Avvio download...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Write-Host '  Download Python in corso...'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe'; Write-Host '  Download completato.'"
if errorlevel 1 (
    echo  ERRORE: download Python fallito. Controlla la connessione.
    pause
    exit /b 1
)

echo  Installazione Python in corso (1-2 minuti)...
"%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_launcher=1
if errorlevel 1 (
    echo  ERRORE: installazione Python fallita.
    pause
    exit /b 1
)
echo  Python installato.

REM Prova percorsi noti di Python senza riavviare
set "PYTHON_CMD="
if exist "C:\Program Files\Python311\python.exe"                         set "PYTHON_CMD=C:\Program Files\Python311\python.exe"
if exist "C:\Python311\python.exe"                                        set "PYTHON_CMD=C:\Python311\python.exe"
if exist "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" set "PYTHON_CMD=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"

if "%PYTHON_CMD%"=="" (
    echo  Python installato ma percorso non trovato automaticamente.
    echo  Apri un nuovo terminale e riesegui build_exe.bat
    pause
    exit /b 1
)
echo  Python trovato in: %PYTHON_CMD%
goto STEP2

:PYTHON_OK
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  Trovato: %%v
set "PYTHON_CMD=python"

REM -----------------------------------------------
REM STEP 2: Controlla pip
REM -----------------------------------------------
:STEP2
echo.
echo [2/4] Verifica pip...
"%PYTHON_CMD%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo  pip non trovato. Installazione...
    "%PYTHON_CMD%" -m ensurepip --upgrade
)
for /f "tokens=*" %%v in ('"%PYTHON_CMD%" -m pip --version 2^>^&1') do echo  Trovato: %%v

REM -----------------------------------------------
REM STEP 3: Installa PyInstaller
REM -----------------------------------------------
echo.
echo [3/4] Installazione PyInstaller...
"%PYTHON_CMD%" -m pip install pyinstaller --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  ERRORE: installazione PyInstaller fallita.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('"%PYTHON_CMD%" -m PyInstaller --version 2^>^&1') do echo  PyInstaller versione: %%v

REM -----------------------------------------------
REM STEP 4: Build exe
REM -----------------------------------------------
echo.
echo [4/4] Compilazione exe...

set "ICON_FLAG="
if exist assets\mt5_icon.ico set "ICON_FLAG=--icon assets\mt5_icon.ico"

if "%ICON_FLAG%"=="" (
    echo  Nessuna icona trovata - build senza icona
) else (
    echo  Icona: assets\mt5_icon.ico
)

echo  Avvio PyInstaller...
echo.

"%PYTHON_CMD%" -m PyInstaller --onefile --uac-admin --console ^
  --add-data "mt5_tool.py;." ^
  --name setup_mt5_vps_0.6.1 ^
  %ICON_FLAG% ^
  setup_vps_installer.py

echo.
if exist dist\setup_mt5_vps_0.6.1.exe (
    echo ============================================
    echo  BUILD COMPLETATA: dist\setup_mt5_vps_0.6.1.exe
    echo ============================================
) else (
    echo ============================================
    echo  ERRORE: build fallita. Vedi messaggi sopra.
    echo ============================================
)

echo.
pause
