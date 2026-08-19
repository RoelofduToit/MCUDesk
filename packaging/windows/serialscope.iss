#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "MCUDesk"
#define AppPublisher "Roelof du Toit"
#define AppExeName "MCUDesk.exe"

[Setup]
; Stable product identity. Do not change this AppId: it is required for
; upgrades from SerialScope to MCUDesk as the same installed application.
AppId={{E893C988-663D-46E8-8C25-E4B83C414F1E}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}

AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/RoelofduToit/MCUDesk
AppSupportURL=https://github.com/RoelofduToit/MCUDesk
AppUpdatesURL=https://github.com/RoelofduToit/MCUDesk/releases

; New installs use MCUDesk. Upgrades keep the previous directory because
; UsePreviousAppDir is yes with this unchanged AppId.
UsePreviousAppDir=yes
DefaultDirName={autopf}\MCUDesk
DefaultGroupName=MCUDesk

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

PrivilegesRequired=admin

OutputDir=..\..\dist\installer
OutputBaseFilename=MCUDesk_{#AppVersion}_Windows_x64_Setup

SetupIconFile=..\..\assets\icons\mcudesk.ico
UninstallDisplayIcon={app}\MCUDesk.exe

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

DisableProgramGroupPage=yes
AllowNoIcons=yes

CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\MCUDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{app}\SerialScope.exe"
Type: files; Name: "{autoprograms}\SerialScope\SerialScope.lnk"
Type: files; Name: "{autodesktop}\SerialScope.lnk"
Type: dirifempty; Name: "{autoprograms}\SerialScope"

[Icons]
Name: "{autoprograms}\MCUDesk"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\MCUDesk"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch MCUDesk"; Flags: nowait postinstall skipifsilent
