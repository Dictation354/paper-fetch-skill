#define AppPublisher "paper-fetch-skill"
#define AppURL "https://github.com/"

#ifndef SourceDir
#define SourceDir "..\.offline-build\paper-fetch-standalone"
#endif

#ifndef AppVersion
#define AppVersion "1.0.0"
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
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\windows-installer-helper.ps1"" -Action Install"; StatusMsg: "Configuring Paper Fetch Skill..."; Flags: runhidden waituntilterminated
Filename: "notepad.exe"; Parameters: """{app}\offline.env"""; Description: "Open offline.env to set ELSEVIER_API_KEY"; Flags: postinstall skipifsilent unchecked nowait

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\windows-installer-helper.ps1"" -Action Uninstall"; Flags: runhidden waituntilterminated

[Code]
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
  end;
end;
