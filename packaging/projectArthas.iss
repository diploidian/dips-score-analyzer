; Inno Setup script for the projectArthas desktop app. Build with packaging\build.ps1.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F2C1B7A-3D4E-4A8B-9C1D-2E5F7A9B0C3D}
AppName=projectArthas
AppVersion={#AppVersion}
AppPublisher=dot.orbital
DefaultDirName={autopf}\projectArthas
DefaultGroupName=projectArthas
DisableProgramGroupPage=yes
; "Only for me" by default, with the "all users" choice offered on a page
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=projectArthas-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\src\dips_score\ui\icon.ico
UninstallDisplayIcon={app}\projectArthas.exe
ChangesEnvironment=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\build\pyinstaller\projectArthas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; the in-game add-on goes in too, so one installer is all a player needs
Source: "..\addon\dips-Score\*"; DestDir: "{code:WowDir}\Interface\AddOns\dips-Score"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: AddonNotLinked

[InstallDelete]
; an upgrade from when the app was called dips score
Type: files; Name: "{app}\dips-score.exe"
Type: files; Name: "{autoprograms}\dips score.lnk"
Type: files; Name: "{autodesktop}\dips score.lnk"

[Icons]
Name: "{autoprograms}\projectArthas"; Filename: "{app}\projectArthas.exe"
Name: "{autodesktop}\projectArthas"; Filename: "{app}\projectArthas.exe"; Tasks: desktopicon

[Registry]
; the app reads the game folder from DIPS_WOW (see src/dips_score/config.py)
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "DIPS_WOW"; ValueData: "{code:WowDir}"; Flags: uninsdeletevalue

[Run]
; the installer's own environment predates DIPS_WOW, so hand the folder over directly
Filename: "{app}\projectArthas.exe"; Parameters: "--wow ""{code:WowDir}"""; Description: "{cm:LaunchProgram,projectArthas}"; Flags: nowait postinstall skipifsilent

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

// On a dev PC AddOns\dips-Score is a junction into the source; writing (or uninstalling) through it would clobber the source.
function AddonNotLinked: Boolean;
var
  R: TFindRec;
begin
  Result := True;
  if FindFirst(AddBackslash(WowDir('')) + 'Interface\AddOns\dips-Score', R) then
  begin
    Result := (R.Attributes and $400) = 0;  // FILE_ATTRIBUTE_REPARSE_POINT
    FindClose(R);
  end;
end;
