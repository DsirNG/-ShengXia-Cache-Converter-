#define AppName "NCM Converter"
#define AppVersion "0.2.0-rc.1"
#define AppExeName "NCM-Converter.exe"

[Setup]
AppId={{A6D3A9D1-5B28-4E86-9E2E-03C974DC9331}
AppName={#AppName}
AppVersion={#AppVersion}
LicenseFile=..\LICENSE
AppPublisher=DsirNG
VersionInfoVersion=0.2.0.0
DefaultDirName={localappdata}\Programs\ShengXiaCacheConverter
DisableDirPage=no
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
WizardStyle=modern
SetupIconFile=..\assets\shengxia.ico
OutputDir=..\artifacts
OutputBaseFilename=NCM-Converter-{#AppVersion}-Windows-x64-Setup
Compression=lzma2/fast
SolidCompression=yes
Uninstallable=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "chinesesimp"; MessagesFile: "Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："; Flags: unchecked

[Files]
Source: "..\build\app\NCM-Converter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动{#AppName}"; Flags: postinstall nowait skipifsilent

