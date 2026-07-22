#define AppPublisher "paper-fetch-skill"
#define AppURL "https://github.com/"

#ifndef SourceDir
#define SourceDir "..\.offline-build\paper-fetch-standalone"
#endif

#ifndef AppVersion
#define AppVersion "3.2.0"
#endif

#ifndef OutputDir
#define OutputDir "..\dist"
#endif

#ifndef SetupBaseName
#define SetupBaseName "paper-fetch-skill-windows-x86_64-setup"
#endif

[Setup]
AppId={{0C1D5E4F-7C6F-4B70-8F9E-8A1AC1E27C0D}
AppName=Paper Fetch Skill
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={localappdata}\PaperFetchSkill
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename={#SetupBaseName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
UninstallDisplayName=Paper Fetch Skill

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "offline.env"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\offline.env"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Run]
Filename: "notepad.exe"; Parameters: """{app}\offline.env"""; Description: "Open offline.env to set ELSEVIER_API_KEY"; Flags: postinstall skipifsilent unchecked nowait

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\windows-installer-helper.ps1"" -Action Uninstall"; Flags: runhidden waituntilterminated

[Code]
var
  OfflineEnvBackupPath: String;
  PostInstallHelperLogPath: String;
  PostInstallHelperWarning: Boolean;
  UpgradePrepared: Boolean;

function SplitCommandLine(CommandLine: String; var FileName: String; var Params: String): Boolean;
var
  I: Integer;
begin
  CommandLine := Trim(CommandLine);
  FileName := '';
  Params := '';

  if CommandLine = '' then
  begin
    Result := False;
    exit;
  end;

  if Copy(CommandLine, 1, 1) = '"' then
  begin
    I := 2;
    while (I <= Length(CommandLine)) and (Copy(CommandLine, I, 1) <> '"') do
      I := I + 1;
    FileName := Copy(CommandLine, 2, I - 2);
    Params := Trim(Copy(CommandLine, I + 1, Length(CommandLine)));
  end
  else
  begin
    I := Pos(' ', CommandLine);
    if I = 0 then
      FileName := CommandLine
    else
    begin
      FileName := Copy(CommandLine, 1, I - 1);
      Params := Trim(Copy(CommandLine, I + 1, Length(CommandLine)));
    end;
  end;

  Result := FileName <> '';
end;

function QueryOldUninstallCommand(var CommandLine: String): Boolean;
var
  UninstallKey: String;
begin
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{0C1D5E4F-7C6F-4B70-8F9E-8A1AC1E27C0D}_is1';
  Result :=
    RegQueryStringValue(HKCU, UninstallKey, 'QuietUninstallString', CommandLine) or
    RegQueryStringValue(HKCU, UninstallKey, 'UninstallString', CommandLine) or
    RegQueryStringValue(HKLM, UninstallKey, 'QuietUninstallString', CommandLine) or
    RegQueryStringValue(HKLM, UninstallKey, 'UninstallString', CommandLine);
end;

procedure BackupOfflineEnv;
var
  OfflineEnvPath: String;
begin
  OfflineEnvPath := ExpandConstant('{app}\offline.env');
  OfflineEnvBackupPath := '';
  if FileExists(OfflineEnvPath) then
  begin
    OfflineEnvBackupPath := ExpandConstant('{tmp}\paper-fetch-offline.env.backup');
    if not FileCopy(OfflineEnvPath, OfflineEnvBackupPath, False) then
      Log('Could not back up existing offline.env before upgrade: ' + OfflineEnvPath);
  end;
end;

procedure RestoreOfflineEnv;
var
  OfflineEnvPath: String;
begin
  if (OfflineEnvBackupPath <> '') and FileExists(OfflineEnvBackupPath) then
  begin
    OfflineEnvPath := ExpandConstant('{app}\offline.env');
    ForceDirectories(ExtractFileDir(OfflineEnvPath));
    if FileCopy(OfflineEnvBackupPath, OfflineEnvPath, False) then
      Log('Restored existing offline.env before post-install helper.')
    else
      Log('Could not restore existing offline.env from backup: ' + OfflineEnvBackupPath);
  end;
end;

procedure RunPostInstallHelper;
var
  HelperPath: String;
  Params: String;
  ResultCode: Integer;
begin
  HelperPath := ExpandConstant('{app}\scripts\windows-installer-helper.ps1');
  PostInstallHelperLogPath := ExpandConstant('{app}\install-helper.log');
  Params := '-NoProfile -ExecutionPolicy Bypass -File "' + HelperPath + '" -Action Install -LogPath "' + PostInstallHelperLogPath + '"';
  Log('Running Paper Fetch Skill post-install helper.');
  if not Exec('powershell.exe', Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    PostInstallHelperWarning := True;
    Log('Could not execute Paper Fetch Skill post-install helper. See ' + PostInstallHelperLogPath + ' if it exists.');
  end
  else if ResultCode <> 0 then
  begin
    PostInstallHelperWarning := True;
    Log('Paper Fetch Skill post-install helper returned exit code ' + IntToStr(ResultCode) + '. Runtime files remain installed; see ' + PostInstallHelperLogPath + '.');
  end;
end;

procedure RunOldUninstaller;
var
  CommandLine: String;
  FileName: String;
  Params: String;
  ResultCode: Integer;
begin
  if not QueryOldUninstallCommand(CommandLine) then
    exit;

  if not SplitCommandLine(CommandLine, FileName, Params) then
  begin
    Log('Could not parse old uninstall command: ' + CommandLine);
    exit;
  end;

  if Pos('/VERYSILENT', Uppercase(Params)) = 0 then
    Params := Trim(Params + ' /VERYSILENT /SUPPRESSMSGBOXES /NORESTART');

  Log('Running old Paper Fetch Skill uninstaller: ' + FileName);
  if not Exec(FileName, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Log('Could not execute old uninstaller.')
  else if ResultCode <> 0 then
    Log('Old uninstaller exited with code ' + IntToStr(ResultCode) + '.');
end;

procedure CleanOldInstallDirectory;
var
  AppDir: String;
begin
  AppDir := ExpandConstant('{app}');
  if DirExists(AppDir) then
  begin
    Log('Cleaning old Paper Fetch Skill install directory: ' + AppDir);
    DelTree(AppDir, True, True, True);
  end;
end;

procedure PrepareUpgradeInstall;
begin
  if UpgradePrepared then
    exit;
  UpgradePrepared := True;

  BackupOfflineEnv;
  RunOldUninstaller;
  CleanOldInstallDirectory;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    PrepareUpgradeInstall
  else if CurStep = ssPostInstall then
  begin
    RestoreOfflineEnv;
    RunPostInstallHelper;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  OfflineEnvPath: String;
begin
  if CurPageID = wpFinished then
  begin
    OfflineEnvPath := ExpandConstant('{app}\offline.env');
    WizardForm.FinishedLabel.Caption :=
      WizardForm.FinishedLabel.Caption + #13#10#13#10 +
      'Elsevier setup: request an API key at https://dev.elsevier.com/ before fetching Elsevier full text.' + #13#10 +
      'Then edit ' + OfflineEnvPath + ' and set ELSEVIER_API_KEY="...".';
    if PostInstallHelperWarning then
      WizardForm.FinishedLabel.Caption :=
        WizardForm.FinishedLabel.Caption + #13#10#13#10 +
        'Post-install configuration completed with a warning. Runtime files were installed; see ' +
        PostInstallHelperLogPath + ' for details.';
  end;
end;
