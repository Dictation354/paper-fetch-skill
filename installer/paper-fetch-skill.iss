#define AppPublisher "paper-fetch-skill"
#define AppURL "https://github.com/"
#define AppGUID "{0C1D5E4F-7C6F-4B70-8F9E-8A1AC1E27C0D}"

#ifndef SourceDir
#define SourceDir "..\.offline-build\paper-fetch-standalone"
#endif

#ifndef AppVersion
#define AppVersion "6.2.4"
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
WizardSizePercent=120
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

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\windows-installer-helper.ps1"" -Action Uninstall"; Flags: runhidden waituntilterminated

[UninstallDelete]
Type: files; Name: "{app}\install-helper.log"

[Code]
var
  OfflineEnvBackupPath: String;
  PostInstallHelperLogPath: String;
  PostInstallHelperWarning: Boolean;
  OptionalCoreReady: Boolean;
  UpgradePrepared: Boolean;
  OptionalPage: TInputQueryWizardPage;
  OptionalToolsPage: TWizardPage;
  OptionalBrowser: TNewCheckBox;
  OptionalGhostscript: TNewCheckBox;
  OptionalVips: TNewCheckBox;
  OptionalProgress: TOutputMarqueeProgressWizardPage;
  OptionalRequestDir: String;
  OptionalResult: String;
  OptionalDone: Boolean;
  CleanupSelected: Boolean;

procedure AddOptionDetails(Page: TWizardPage; Top: Integer; Caption: String);
var
  Details: TNewStaticText;
begin
  Details := TNewStaticText.Create(WizardForm);
  Details.Parent := Page.Surface;
  Details.AutoSize := False;
  Details.SetBounds(ScaleX(20), ScaleY(Top), Page.SurfaceWidth - ScaleX(20), ScaleY(48));
  Details.WordWrap := True;
  Details.Caption := Caption;
end;

procedure InitializeWizard;
begin
  OptionalPage := CreateInputQueryPage(wpInstalling,
    'Optional configuration', 'Core installation is complete. All downloads default to off.',
    'Blank credentials preserve existing values in {app}\offline.env. Inputs are hidden.' + #13#10 +
    'Restart running hosts/MCP afterwards. Skipping Camoufox keeps runtime automatic preparation enabled.');
  OptionalPage.Add('Elsevier API Key (https://dev.elsevier.com/):', True);
  OptionalPage.Add('Wiley TDM Token:', True);
  OptionalToolsPage := CreateCustomPage(OptionalPage.ID, 'Optional tools',
    'Each component is independent. Existing valid tools are reused. All downloads default to off.');
  OptionalBrowser := TNewCheckBox.Create(WizardForm);
  OptionalBrowser.Parent := OptionalToolsPage.Surface;
  OptionalBrowser.SetBounds(0, 0, OptionalToolsPage.SurfaceWidth, ScaleY(20));
  OptionalBrowser.Caption := 'Prepare and locally test Camoufox';
  AddOptionDetails(OptionalToolsPage, 24, 'Network download to user shared cache; no elevation. Skipping keeps runtime automatic preparation enabled.');
  OptionalGhostscript := TNewCheckBox.Create(WizardForm);
  OptionalGhostscript.Parent := OptionalToolsPage.Surface;
  OptionalGhostscript.SetBounds(0, ScaleY(84), OptionalToolsPage.SurfaceWidth, ScaleY(20));
  OptionalGhostscript.Caption := 'Install Ghostscript for EPS conversion (UAC/admin required)';
  AddOptionDetails(OptionalToolsPage, 108, 'Official EXE download to {app}\image-tools\ghostscript\<version>. Visible installer writes system registry.');
  OptionalVips := TNewCheckBox.Create(WizardForm);
  OptionalVips.Parent := OptionalToolsPage.Surface;
  OptionalVips.SetBounds(0, ScaleY(168), OptionalToolsPage.SurfaceWidth, ScaleY(20));
  OptionalVips.Caption := 'Install libvips for TIFF conversion';
  AddOptionDetails(OptionalToolsPage, 192, 'Official ZIP download to {app}\image-tools\libvips\<version>, including DLLs and resources; no elevation.');
  OptionalBrowser.Checked := False;
  OptionalGhostscript.Checked := False;
  OptionalVips.Checked := False;
  OptionalProgress := CreateOutputMarqueeProgressPage('Optional configuration',
    'Core installation is preserved if an optional step fails or is cancelled.');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := ((PageID = OptionalPage.ID) or (PageID = OptionalToolsPage.ID)) and
    (WizardSilent or not OptionalCoreReady);
end;

function ChoiceFlag(Selected: Boolean): String;
begin
  if Selected then Result := '1' else Result := '0';
end;

procedure DeleteOptionalRequest;
begin
  if OptionalRequestDir <> '' then
  begin
    DeleteFile(OptionalRequestDir + '\request.txt');
    DeleteFile(OptionalRequestDir + '\result.txt');
    RemoveDir(OptionalRequestDir);
  end;
end;

procedure RunOptionalConfiguration;
var
  PythonPath, Params, RequestPath, ResultPath: String;
  ResultCode: Integer;
  Lines: TArrayOfString;
  ResultText: AnsiString;
begin
  if WizardSilent or not OptionalCoreReady or OptionalDone then exit;
  OptionalDone := True;
  SetArrayLength(Lines, 5);
  PythonPath := ExpandConstant('{app}\runtime\python.exe');
  OptionalRequestDir := ExpandConstant('{tmp}\paper-fetch-optional');
  RequestPath := OptionalRequestDir + '\request.txt';
  ResultPath := OptionalRequestDir + '\result.txt';
  Params := '-X utf8 -m paper_fetch.offline_setup --install-root "' + ExpandConstant('{app}') + '"';
  OptionalProgress.Show;
  try
    OptionalProgress.SetText('Preparing private configuration input...', '');
    OptionalProgress.Animate;
    { The directory DACL is restricted BEFORE any credential is written. }
    if not Exec(PythonPath, Params + ' --initialize-request "' + OptionalRequestDir + '"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then exit;
    if ResultCode <> 0 then exit;
    Lines[0] := OptionalPage.Values[0];
    Lines[1] := OptionalPage.Values[1];
    Lines[2] := ChoiceFlag(OptionalBrowser.Checked);
    Lines[3] := ChoiceFlag(OptionalGhostscript.Checked);
    Lines[4] := ChoiceFlag(OptionalVips.Checked);
    if not SaveStringsToUTF8File(RequestPath, Lines, False) then exit;
    Lines[0] := ''; Lines[1] := '';
    OptionalPage.Values[0] := ''; OptionalPage.Values[1] := '';
    OptionalProgress.SetText('Checking optional components...',
      'Progress/results appear in the console. Ctrl+C cancels the current optional step.');
    if Exec(PythonPath, Params + ' --request "' + RequestPath + '" --result "' + ResultPath + '"',
      '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
    begin
      if LoadStringFromFile(ResultPath, ResultText) then
        OptionalResult := UTF8Decode(ResultText);
    end;
  finally
    Lines[0] := ''; Lines[1] := '';
    OptionalPage.Values[0] := ''; OptionalPage.Values[1] := '';
    DeleteOptionalRequest;
    OptionalProgress.Hide;
    if OptionalResult = '' then
      OptionalResult := 'Optional configuration was cancelled or could not finish. Core installation remains complete.';
    { Results contain statuses and tool paths only, never credentials. }
    SaveStringToFile(ExpandConstant('{app}\optional-setup-results.txt'), UTF8Encode(OptionalResult), False);
    MsgBox(OptionalResult, mbInformation, MB_OK);
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = OptionalToolsPage.ID then
    RunOptionalConfiguration;
end;

procedure DeinitializeSetup;
begin
  DeleteOptionalRequest;
  if OfflineEnvBackupPath <> '' then DeleteFile(OfflineEnvBackupPath);
end;

procedure InitializeUninstallProgressForm;
var
  Form: TSetupForm;
  CleanupTools: TNewCheckBox;
  ContinueButton: TNewButton;
  Details: TNewStaticText;
begin
  if UninstallSilent then exit;
#if Ver >= 0x06060000
  { Inno Setup 6.6+ requires dimensions at construction; they are read-only. }
  Form := CreateCustomForm(ScaleX(480), ScaleY(150), False, False);
#else
  Form := CreateCustomForm;
#endif
  try
    Form.Caption := 'Optional tools';
#if Ver < 0x06060000
    Form.ClientWidth := ScaleX(480);
    Form.ClientHeight := ScaleY(150);
#endif
    CleanupTools := TNewCheckBox.Create(Form);
    CleanupTools.Parent := Form;
    CleanupTools.SetBounds(ScaleX(20), ScaleY(20), ScaleX(440), ScaleY(20));
    CleanupTools.Caption := 'Remove optional tools owned by this installer (default: keep)';
    CleanupTools.Checked := False;
    Details := TNewStaticText.Create(Form);
    Details.Parent := Form;
    Details.AutoSize := False;
    Details.SetBounds(ScaleX(20), ScaleY(45), ScaleX(440), ScaleY(50));
    Details.WordWrap := True;
    Details.Caption := 'Ghostscript opens its official uninstaller and may require UAC. External tools and user-added libvips files are preserved.';
    ContinueButton := TNewButton.Create(Form);
    ContinueButton.Parent := Form;
    ContinueButton.SetBounds(ScaleX(340), ScaleY(105), ScaleX(120), ScaleY(25));
    ContinueButton.Caption := 'Continue uninstall';
    ContinueButton.Default := True;
    ContinueButton.ModalResult := mrOk;
    CleanupSelected := (Form.ShowModal = mrOk) and CleanupTools.Checked;
  finally
    Form.Free;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if (CurUninstallStep = usUninstall) and not UninstallSilent then
  begin
      if CleanupSelected then
        Exec(ExpandConstant('{app}\runtime\python.exe'),
          '-X utf8 -m paper_fetch.offline_setup --install-root "' + ExpandConstant('{app}') +
          '" --cleanup-tools --result "' + ExpandConstant('{app}\optional-cleanup-results.txt') + '"',
          '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
  end;
end;

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
    if ResultCode = 2 then
    begin
      { Integration warnings do not prevent optional setup when core smoke
        succeeds. Recheck using the existing read-only Smoke action. }
      Params := '-NoProfile -ExecutionPolicy Bypass -File "' + HelperPath + '" -Action Smoke';
      if Exec('powershell.exe', Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
        OptionalCoreReady := ResultCode = 0;
    end;
  end
  else
    OptionalCoreReady := True;
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
    if OptionalResult <> '' then
      WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 +
        'Optional configuration results: ' + ExpandConstant('{app}\optional-setup-results.txt') + #13#10 +
        'Restart running hosts/MCP. Skipping Camoufox keeps runtime automatic preparation enabled.';
  end;
end;
