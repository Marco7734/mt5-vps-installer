#define MyAppName "MT5 Remote Reader"
#define MyAppPublisher "Marco7734"
#define MyAppExeName "MT5RemoteReader.exe"

[Setup]
AppId={{B7F2C4A1-3E8D-4F0B-9C2A-1D5E6F7A8B9C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\MT5RemoteReader
DefaultGroupName={#MyAppName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=Output
OutputBaseFilename=MT5RemoteReader_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Files]
Source: "dist\MT5RemoteReader.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Disinstalla {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Avvia MT5 Remote Reader"; Flags: postinstall nowait

[UninstallRun]
; Ferma e rimuove il servizio OpenSSH
Filename: "powershell.exe"; Parameters: "-Command ""Stop-Service sshd -Force -ErrorAction SilentlyContinue"""; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "-Command ""Remove-Service sshd -ErrorAction SilentlyContinue"""; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "-Command ""Stop-Service ssh-agent -Force -ErrorAction SilentlyContinue"""; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "-Command ""Remove-Service ssh-agent -ErrorAction SilentlyContinue"""; Flags: runhidden waituntilterminated

; Rimuove i file OpenSSH
Filename: "powershell.exe"; Parameters: "-Command ""Remove-Item 'C:\Program Files\OpenSSH' -Recurse -Force -ErrorAction SilentlyContinue"""; Flags: runhidden waituntilterminated

; Rimuove la regola firewall SSH
Filename: "powershell.exe"; Parameters: "-Command ""Remove-NetFirewallRule -DisplayName 'OpenSSH' -ErrorAction SilentlyContinue"""; Flags: runhidden waituntilterminated

; Rimuove mt5_tool.py dal Desktop
Filename: "powershell.exe"; Parameters: "-Command ""Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) 'mt5_tool.py') -Force -ErrorAction SilentlyContinue"""; Flags: runhidden waituntilterminated

; Disinstalla le librerie Python installate dal programma
Filename: "powershell.exe"; Parameters: "-Command ""python -m pip uninstall MetaTrader5 psutil -y 2>$null"""; Flags: runhidden waituntilterminated
