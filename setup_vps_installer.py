"""
setup_vps_installer.py — Installer automatico per VPS Windows MT5
Installa tutto il necessario per usare mt5-remote-reader-mcp:
  1. OpenSSH Server
  2. Python 3.8.10
  3. MetaTrader5 e psutil
  4. mt5_tool.py sul Desktop

Compilare con (su Windows):
    build_exe.bat
"""

import subprocess
import sys
import os
import shutil
import urllib.request
import tempfile
import time
import ctypes

# ── Costanti ──────────────────────────────────────────────────────────────────

PYTHON_URL = "https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe"
PYTHON_INSTALLER = os.path.join(tempfile.gettempdir(), "python-3.8.10-amd64.exe")

OPENSSH_URL = "https://github.com/PowerShell/Win32-OpenSSH/releases/download/v9.5.0.0p1-Beta/OpenSSH-Win64.zip"
OPENSSH_ZIP = os.path.join(tempfile.gettempdir(), "OpenSSH-Win64.zip")
OPENSSH_DIR = r"C:\Program Files\OpenSSH"

MT5_TOOL_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "mt5_tool.py")

# Path python: inizia con "python", aggiornato a path fisso se non è nel PATH dopo l'install
PYTHON_CMD = "python"
PYTHON_KNOWN_PATHS = [
    r"C:\Program Files\Python38\python.exe",
    r"C:\Python38\python.exe",
    r"C:\Users\Administrator\AppData\Local\Programs\Python\Python38\python.exe",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run(cmd, shell=True, check=False):
    result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def log(msg):
    print(f"  → {msg}", flush=True)


def ok(msg):
    print(f"  ✓ {msg}", flush=True)


def err(msg):
    print(f"  ✗ {msg}", flush=True)


def download(url, dest, label):
    log(f"Download {label}...")
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(url, context=ctx) as r, open(dest, "wb") as f:
            f.write(r.read())
        ok(f"{label} scaricato.")
        return True
    except Exception as e:
        err(f"Download fallito: {e}")
        return False


def separator():
    print("-" * 50, flush=True)

# ── Step 1: OpenSSH ───────────────────────────────────────────────────────────

def install_openssh():
    separator()
    print("STEP 1 — OpenSSH Server", flush=True)

    out, _, rc = run('sc query sshd')
    if rc == 0:
        ok("OpenSSH Server gia' installato.")
        _ensure_openssh_running()
        return True

    if not download(OPENSSH_URL, OPENSSH_ZIP, "OpenSSH"):
        return False

    log("Estrazione OpenSSH...")
    out, err_msg, rc = run(
        f'powershell -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; '
        f"[System.IO.Compression.ZipFile]::ExtractToDirectory('{OPENSSH_ZIP}', 'C:\\\\Program Files')\""
    )
    if rc != 0:
        err(f"Estrazione fallita: {err_msg}")
        return False

    run(r'rename "C:\Program Files\OpenSSH-Win64" OpenSSH')

    log("Installazione OpenSSH...")
    out, err_msg, rc = run(
        r'powershell -ExecutionPolicy Bypass -File "C:\Program Files\OpenSSH\install-sshd.ps1"'
    )
    if rc != 0:
        err(f"Installazione OpenSSH fallita: {err_msg}")
        return False

    ok("OpenSSH installato.")
    _ensure_openssh_running()
    return True


def _ensure_openssh_running():
    log("Avvio servizio SSH...")
    run("net start sshd")
    run('sc config sshd start= auto')
    run('sc config ssh-agent start= auto')
    run("net start ssh-agent")

    log("Apertura porta 22 nel firewall...")
    run(
        'netsh advfirewall firewall add rule name="OpenSSH" '
        'dir=in action=allow protocol=TCP localport=22'
    )
    ok("SSH avviato e porta 22 aperta.")

# ── Step 2: Python ────────────────────────────────────────────────────────────

def install_python():
    separator()
    print("STEP 2 — Python 3.8", flush=True)

    out, _, rc = run("python --version")
    if rc == 0 and "Python" in out:
        ok(f"Python gia' installato: {out}")
        return True

    if not download(PYTHON_URL, PYTHON_INSTALLER, "Python 3.8.10"):
        return False

    log("Installazione Python (potrebbe richiedere 1-2 minuti)...")
    _, err_msg, rc = run(
        f'"{PYTHON_INSTALLER}" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0'
    )
    if rc not in (0, 1641, 3010):
        err(f"Installazione Python fallita (code {rc}): {err_msg}")
        return False

    time.sleep(5)
    global PYTHON_CMD
    out, _, rc = run("python --version")
    if rc == 0 and "Python" in out:
        ok(f"Python installato: {out}")
        return True

    for path in PYTHON_KNOWN_PATHS:
        if os.path.isfile(path):
            PYTHON_CMD = f'"{path}"'
            out, _, rc = run(f'{PYTHON_CMD} --version')
            if rc == 0 and "Python" in out:
                ok(f"Python installato (path diretto): {out}")
                return True

    err("Python installato ma non trovato. Riavvia la VPS e rilancia.")
    return False

# ── Step 3: Librerie Python ───────────────────────────────────────────────────

def install_libraries():
    separator()
    print("STEP 3 — Librerie Python", flush=True)

    log("Installazione MetaTrader5...")
    _, err_msg, rc = run(f"{PYTHON_CMD} -m pip install MetaTrader5 --quiet")
    if rc != 0:
        err(f"MetaTrader5 fallito: {err_msg}")
        return False
    ok("MetaTrader5 installato.")

    log("Installazione psutil...")
    _, err_msg, rc = run(f"{PYTHON_CMD} -m pip install psutil --quiet")
    if rc != 0:
        err(f"psutil fallito: {err_msg}")
        return False
    ok("psutil installato.")

    return True

# ── Step 4: mt5_tool.py ───────────────────────────────────────────────────────

def deploy_mt5_tool():
    separator()
    print("STEP 4 — mt5_tool.py", flush=True)

    # Legge mt5_tool.py dal bundle (PyInstaller) o dalla stessa directory dello script
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS  # directory temporanea di PyInstaller
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    source = os.path.join(base_path, "mt5_tool.py")
    if not os.path.isfile(source):
        err(f"mt5_tool.py non trovato in {source}")
        return False

    shutil.copy(source, MT5_TOOL_PATH)
    ok(f"mt5_tool.py copiato in {MT5_TOOL_PATH}")
    return True

# ── Step 5: Test ──────────────────────────────────────────────────────────────

def test_setup():
    separator()
    print("STEP 5 — Test finale", flush=True)

    log("Test connessione MT5...")
    out, err_msg, rc = run(f'{PYTHON_CMD} "{MT5_TOOL_PATH}" --function list_terminals')

    if out and out.startswith("{"):
        ok("MT5 risponde correttamente!")
        print(f"\n  Terminali trovati:\n{out}\n", flush=True)
        return True
    else:
        log("MT5 non risponde — assicurati che MetaTrader 5 sia aperto e loggato.")
        if err_msg:
            log(f"Dettaglio: {err_msg}")
        ok("Setup completato — apri MT5 e riprova la connessione da Claude.")
        return True

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 50, flush=True)
    print("  mt5-remote-reader-mcp — Setup VPS", flush=True)
    print("=" * 50 + "\n", flush=True)

    if not is_admin():
        err("Questo installer richiede i privilegi di Amministratore.")
        err("Tasto destro sull'exe → 'Esegui come amministratore'")
        input("\nPremi INVIO per uscire...")
        sys.exit(1)

    steps = [
        install_openssh,
        install_python,
        install_libraries,
        deploy_mt5_tool,
        test_setup,
    ]

    for step in steps:
        if not step():
            separator()
            err("Setup interrotto. Controlla gli errori sopra.")
            input("\nPremi INVIO per uscire...")
            sys.exit(1)

    # Rileva IP pubblico della VPS
    vps_ip = "YOUR_VPS_IP"
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen("https://api.ipify.org", context=ctx) as r:
            vps_ip = r.read().decode().strip()
    except Exception:
        pass

    print("\n" + "=" * 50, flush=True)
    print("  Fatto! La VPS e' pronta.", flush=True)
    print("=" * 50, flush=True)
    print(flush=True)
    print("  Puoi chiudere questa finestra e tornare", flush=True)
    print("  alla tua sessione Claude.", flush=True)
    print(flush=True)
    print("  Scrivi 'fatto' e Claude completera'", flush=True)
    print("  la connessione automaticamente.", flush=True)
    print(flush=True)
    input("Premi INVIO per chiudere...")


if __name__ == "__main__":
    main()
