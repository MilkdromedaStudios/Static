#ifndef MyAppVersion
  #error Pass /DMyAppVersion=x.y.z
#endif

[Setup]
AppId={{E58E7B31-94D3-4E64-B724-5AC9199D4A83}
AppName=Static
AppVersion={#MyAppVersion}
AppPublisher=Milkdromeda Studios
AppPublisherURL=https://github.com/MilkdromedaStudios/Static
AppSupportURL=https://github.com/MilkdromedaStudios/Static/issues
AppUpdatesURL=https://github.com/MilkdromedaStudios/Static/releases/latest
DefaultDirName={localappdata}\Programs\Static
DefaultGroupName=Static
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19044
OutputDir=..\release
OutputBaseFilename=Static-{#MyAppVersion}-Windows-x64-Setup
SetupIconFile=..\build\branding\static.ico
UninstallDisplayIcon={app}\Static.exe
UninstallDisplayName=Static
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallLogging=yes

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Static\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Static"; Filename: "{app}\Static.exe"
Name: "{group}\Uninstall Static"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Static"; Filename: "{app}\Static.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: StaticAI; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Static.exe"; Description: "Open Static"; Flags: nowait postinstall skipifsilent

[Code]
var RemoveWorkspace: Boolean;

function CloseStatic(): Boolean;
var Code: Integer;
begin
  Result := True;
  if FileExists(ExpandConstant('{app}\Static.exe')) then begin
    Result := Exec(ExpandConstant('{app}\Static.exe'), '--quit', '', SW_HIDE, ewWaitUntilTerminated, Code);
    if Result then Result := Code = 0;
    if not Result then MsgBox('Static is still preparing a local model. Finish that installer or download, quit Static, then try again.', mbError, MB_OK);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not CloseStatic() then Result := 'Quit Static before updating it.';
end;

function InitializeUninstall(): Boolean;
begin
  Result := CloseStatic();
  RemoveWorkspace := False;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Code: Integer;
begin
  if CurUninstallStep = usUninstall then begin
    if not UninstallSilent then
      RemoveWorkspace := MsgBox('Also delete your Static chats, generated files, preferences and browser data?' + #13#10 + #13#10 + 'Choose No to keep them for a future installation. Saved API keys are removed in either case. Shared software such as Ollama stays installed.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
    if not Exec(ExpandConstant('{app}\Static.exe'), '--cleanup-credentials', '', SW_HIDE, ewWaitUntilTerminated, Code) then
      RaiseException('Could not remove saved API keys. Close Static and try uninstalling again.');
    if Code <> 0 then
      RaiseException('Windows could not remove saved API keys. Check desktop.log and try again.');
  end;
  if (CurUninstallStep = usPostUninstall) and RemoveWorkspace then
    DelTree(ExpandConstant('{localappdata}\StaticAI'), True, True, True);
end;
