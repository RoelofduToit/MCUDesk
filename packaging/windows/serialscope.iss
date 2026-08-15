#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "SerialScope"
#define AppPublisher "Roelof du Toit"
#define AppExeName "SerialScope.exe"

[Setup]
AppId={{E893C988-663D-46E8-8C25-E4B83C414F1E}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}

AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/RoelofduToit/SerialScope
AppSupportURL=https://github.com/RoelofduToit/SerialScope
AppUpdatesURL=https://github.com/RoelofduToit/SerialScope/releases

DefaultDirName={autopf}\SerialScope
DefaultGroupName=SerialScope

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

PrivilegesRequired=admin

OutputDir=..\..\dist\installer
OutputBaseFilename=SerialScope_{#AppVersion}_Windows_x64_Setup

SetupIconFile=..\..\assets\icons\serialscope.ico
UninstallDisplayIcon={app}\SerialScope.exe

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
Source: "..\..\dist\SerialScope\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SerialScope"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\SerialScope"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch SerialScope"; Flags: nowait postinstall skipifsilent