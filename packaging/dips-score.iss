; Inno Setup script for the dips score desktop app. Build with packaging\build.ps1.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F2C1B7A-3D4E-4A8B-9C1D-2E5F7A9B0C3D}
AppName=dips score
AppVersion={#AppVersion}
AppPublisher=dot.orbital
DefaultDirName={autopf}\dips score
DefaultGroupName=dips score
DisableProgramGroupPage=yes
; "Only for me" by default, with the "all users" choice offered on a page
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=dips-score-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\dips-score.exe
ChangesEnvironment=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\build\pyinstaller\dips-score\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\dips score"; Filename: "{app}\dips-score.exe"
Name: "{autodesktop}\dips score"; Filename: "{app}\dips-score.exe"; Tasks: desktopicon

[Registry]
; the app reads the game folder from DIPS_WOW (see src/dips_score/config.py)
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "DIPS_WOW"; ValueData: "{code:WowDir}"; Flags: uninsdeletevalue

[Run]
; the installer's own environment predates DIPS_WOW, so hand the folder over directly
Filename: "{app}\dips-score.exe"; Parameters: "--wow ""{code:WowDir}"""; Description: "{cm:LaunchProgram,dips score}"; Flags: nowait postinstall skipifsilent

[Code]
var
  WowPage: TInputDirWizardPage;

function GuessWow: String;
begin
  Result := GetEnv('DIPS_WOW');
  if Result = '' then
    Result := 'C:\Program Files (x86)\World of Warcraft\_forever_';
end;

procedure InitializeWizard;
begin
  WowPage := CreateInputDirPage(wpSelectDir, 'World of Warcraft folder',
    'Where is the game installed?',
    'Pick the _forever_ folder (the one with Logs, WTF and Interface in it).', False, '');
  WowPage.Add('');
  WowPage.Values[0] := GuessWow;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = WowPage.ID) and not DirExists(AddBackslash(WowPage.Values[0]) + 'WTF') then
    Result := MsgBox('There is no WTF folder in that one, so it may not be the game folder. Use it anyway?',
      mbConfirmation, MB_YESNO) = IDYES;
end;

function WowDir(Param: String): String;
begin
  Result := WowPage.Values[0];
end;
