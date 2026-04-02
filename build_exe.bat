@echo off
REM build_exe.bat — Compila MT5RemoteReader.exe e MT5RemoteReader_Setup_X.X.X.exe
REM Installa automaticamente Python, PyInstaller e Inno Setup se mancanti

echo.
echo ============================================
echo  MT5 Remote Reader -- Build Installer
echo ============================================
echo.

REM -----------------------------------------------
REM STEP 1: Controlla se Python e' disponibile
REM -----------------------------------------------
echo [1/5] Verifica Python...
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
echo [2/5] Verifica pip...
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
echo [3/5] Installazione PyInstaller...
"%PYTHON_CMD%" -m pip install pyinstaller --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  ERRORE: installazione PyInstaller fallita.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('"%PYTHON_CMD%" -m PyInstaller --version 2^>^&1') do echo  PyInstaller versione: %%v

REM -----------------------------------------------
REM STEP 4: Build exe con PyInstaller
REM -----------------------------------------------
echo.
echo [4/5] Compilazione MT5RemoteReader.exe...

REM Legge la versione da setup_vps_installer.py automaticamente
for /f "delims=" %%v in ('powershell -Command "(Select-String -Path setup_vps_installer.py -Pattern '__version__').Line.Split(chr(34))[1]"') do set VERSION=%%v
if "%VERSION%"=="" (
    echo  ERRORE: versione non trovata in setup_vps_installer.py
    pause
    exit /b 1
)
echo  Versione rilevata: %VERSION%

set "ICON_FLAG="
if exist assets\mt5_icon.ico set "ICON_FLAG=--icon assets\mt5_icon.ico"

"%PYTHON_CMD%" -m PyInstaller --onefile --uac-admin --console ^
  --add-data "mt5_tool.py;." ^
  --name MT5RemoteReader ^
  %ICON_FLAG% ^
  setup_vps_installer.py

if not exist dist\MT5RemoteReader.exe (
    echo  ERRORE: PyInstaller fallito.
    pause
    exit /b 1
)
echo  MT5RemoteReader.exe creato.

REM -----------------------------------------------
REM STEP 5: Build installer con Inno Setup
REM -----------------------------------------------
echo.
echo [5/5] Creazione installer con Inno Setup...

set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo  Inno Setup non trovato. Installazione tramite winget...
    winget install JRSoftware.InnoSetup --silent
    if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo  ERRORE: Inno Setup non trovato. Scaricalo da https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

"%ISCC%" /DMyAppVersion=%VERSION% installer.iss

echo.
if exist Output\MT5RemoteReader_Setup_%VERSION%.exe (
    echo ============================================
    echo  BUILD COMPLETATA!
    echo  Output\MT5RemoteReader_Setup_%VERSION%.exe
    echo ============================================
) else (
    echo ============================================
    echo  ERRORE: build installer fallita.
    echo ============================================
)

echo.
pause
