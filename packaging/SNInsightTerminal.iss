#define MyAppName "SNInsightTerminal"
#define MyAppVersion "0.4.3-private-research-beta.1"
#define MyAppPublisher "SNInsightTerminal"
#define MyAppExeName "SNInsightTerminal.exe"

[Setup]
AppId={{74C4F9CE-5B83-4B6F-82F8-5E9B6241C001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SNInsightTerminal
DefaultGroupName=SNInsightTerminal
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=SNInsightTerminal_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\SNInsightTerminal\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{app}\_internal\private\private_bundle_seed.json"
Type: files; Name: "{app}\_internal\private\private_release_keys.json"
Type: files; Name: "{app}\_internal\private\secrets.json"
Type: files; Name: "{app}\_internal\private\.env"
Type: dirifempty; Name: "{app}\_internal\private"

[Icons]
Name: "{group}\SNInsightTerminal"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\SNInsightTerminal"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SNInsightTerminal"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
