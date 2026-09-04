#define AppName "Third Way Temporary Node"
#define AppVersion "0.1.0"
#define AppPublisher "Third Way Project"
#define AppExeName "ThirdWayNode.exe"

[Setup]
AppId={{D7276150-AB5E-4D6B-83E4-8F6F412E8A96}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/trynottopanic/HGttG_vol1
DefaultDirName={localappdata}\Programs\ThirdWayNode
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\installer-dist
OutputBaseFilename=ThirdWayNode-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern dynamic
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
InfoBeforeFile=..\NODE-PRIVACY.txt
LicenseFile=..\..\..\LICENSES\AGPL-3.0-or-later.txt
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\OWNER-INSTRUCTIONS.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\NODE-PRIVACY.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Read what this Node does"; Filename: "{app}\NODE-PRIVACY.txt"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Optional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent
