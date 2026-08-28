#define AppPublisher "paper-fetch-skill"
#define AppURL "https://github.com/"
#define AppGUID "{0C1D5E4F-7C6F-4B70-8F9E-8A1AC1E27C0D}"

#ifndef SourceDir
#define SourceDir "..\.offline-build\paper-fetch-standalone"
#endif

#ifndef AppVersion
#define AppVersion "6.0.0"
#endif

#ifndef OutputDir
#define OutputDir "..\dist"
#endif

#ifndef SetupBaseName
#define SetupBaseName "paper-fetch-skill-windows-x86_64-setup"
#endif

[Setup]
AppId={{#AppGUID}
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
Source: "vendor\uninsis\i386\UninsIS.dll"; Flags: dontcopy
Source: "vendor\uninsis\LICENSE"; DestDir: "{app}\licenses"; DestName: "UninsIS-LGPL-3.0.txt"; Flags: ignoreversion
Source: "vendor\uninsis\NOTICE.md"; DestDir: "{app}\licenses"; DestName: "UninsIS-NOTICE.md"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "offline.env"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\offline.env"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist uninsneveruninstall

[Run]
Filename: "notepad.exe"; Parameters: """{app}\offline.env"""; Description: "Open offline.env to set ELSEVIER_API_KEY"; Flags: postinstall skipifsilent unchecked nowait

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\windows-installer-helper.ps1"" -Action Uninstall"; Flags: runhidden waituntilterminated

[UninstallDelete]
Type: files; Name: "{app}\install-helper.log"

[Code]
var
  OfflineEnvBackupPath: String;
  PostInstallHelperLogPath: String;
  PostInstallHelperWarning: Boolean;
  UpgradePrepared: Boolean;

function DLLIsISPackageInstalled(AppId: String; Is64BitInstallMode,
  IsAdminInstallMode: DWORD): DWORD;
  external 'IsISPackageInstalled@files:UninsIS.dll stdcall setuponly';

function DLLUninstallISPackage(AppId: String; Is64BitInstallMode,
  IsAdminInstallMode: DWORD): DWORD;
  external 'UninstallISPackage@files:UninsIS.dll stdcall setuponly';

procedure BackupOfflineEnv;
var
  OfflineEnvPath: String;
begin
  OfflineEnvPath := ExpandConstant('{app}\offline.env');
  if (OfflineEnvBackupPath <> '') and FileExists(OfflineEnvBackupPath) then
    exit;
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

function RunOldUninstaller: String;
var
  ResultCode: DWORD;
begin
  Result := '';
  if DLLIsISPackageInstalled(
    '{#AppGUID}',
    DWORD(Is64BitInstallMode()),
    DWORD(IsAdminInstallMode())
  ) <> 1 then
    exit;

  Log('Uninstalling the existing Paper Fetch Skill package with UninsIS.dll.');
  ResultCode := DLLUninstallISPackage(
    '{#AppGUID}',
    DWORD(Is64BitInstallMode()),
    DWORD(IsAdminInstallMode())
  );
  if ResultCode <> 0 then
  begin
    Result :=
      'Could not completely uninstall the existing Paper Fetch Skill package ' +
      '(UninsIS error ' + IntToStr(Integer(ResultCode)) + '). ' +
      'Setup will not continue while old uninstall cleanup may still be active.';
    Log(Result);
  end
  else
    Log(
      'UninsIS.dll confirmed that the existing package uninstaller ' +
      'completed and deleted its original executable.'
    );
end;

procedure CleanOldInstallDirectory;
var
  AppDir: String;
begin
  AppDir := ExpandConstant('{app}');
  if DirExists(AppDir) then
  begin
    if RemoveDir(AppDir) then
      Log('Removed empty old Paper Fetch Skill install directory: ' + AppDir)
    else
      Log('Preserving user-owned content in old Paper Fetch Skill install directory: ' + AppDir);
  end;
end;

function PrepareUpgradeInstall: String;
begin
  Result := '';
  if UpgradePrepared then
    exit;

  BackupOfflineEnv;
  Result := RunOldUninstaller;
  if Result <> '' then
    exit;
  CleanOldInstallDirectory;
  UpgradePrepared := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := PrepareUpgradeInstall;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
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
