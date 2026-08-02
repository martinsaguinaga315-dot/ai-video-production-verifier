#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif
#ifndef MyAppName
  #define MyAppName "AI Video Production Verifier"
#endif
#define MyAppPublisher "Muzifan AIGC"
#define MyAppExeName MyAppName + ".exe"
[Setup]
AppId={{2C5303E9-94B6-4F8C-A4D7-8CD9A4EED679}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\AIVideoProductionVerifier
DefaultGroupName={#MyAppName}
OutputBaseFilename=AI-Video-Production-Verifier-Setup-v{#MyAppVersion}
OutputDir=..\release
SetupIconFile=..\assets\app.ico
LicenseFile=..\LICENSE
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "..\release\installer-stage\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional options:"
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
