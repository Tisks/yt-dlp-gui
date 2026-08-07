; Inno Setup script -- builds the shareable yt-dlp-gui installer .exe
; Compile with: ISCC.exe packaging\windows\installer.iss
; Override the version with: ISCC.exe /DAppVersion=1.2.3 ...

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#define AppName "yt-dlp-gui"
#define AppExeName "yt-dlp-gui.exe"

[Setup]
AppId={{8F3C1B7E-2D64-4A19-9E8B-5C7A0D6F4B21}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Default to a per-user install so no UAC prompt appears; the user can still
; elevate to a machine-wide install from the dialog if they want one.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\dist\windows
OutputBaseFilename={#AppName}-{#AppVersion}-setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; The whole PyInstaller onedir output, including _internal\tools\bin
Source: "..\..\dist\windows\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
