; Inno Setup script for VajraStocks Windows installer
; Produces: VajraStocks-Setup.exe

#define AppName      "VajraStocks"
#define AppPublisher "Abhishek Kumar"
#define AppURL       "https://github.com/abhishek4official/VajraStocks"
#define AppExeName   "VajraStocks.exe"
#define SrcDir       "..\..\dist\VajraStocks"
#define IconFile     "..\assets\icon.ico"

#define AppVersion GetEnv("APP_VERSION")
#if AppVersion == ""
  #define AppVersion "1.2.0"
#endif

[Setup]
; Keep AppId fixed forever — changing it creates a second Add/Remove Programs entry
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Show in Add/Remove Programs with publisher, version, URL, and estimated size
CreateUninstallRegKey=yes
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}
#if FileExists(IconFile)
SetupIconFile={#IconFile}
#endif
OutputDir=..\..\release
OutputBaseFilename=VajraStocks-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Require admin so we can write to Program Files
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; Kill running instances and warn the user before install/upgrade
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start VajraStocks automatically at Windows login"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Always overwrite — ensures old files are fully replaced on upgrade
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the runtime data folder created by the app
Type: filesandordirs; Name: "{app}\data"

[Code]
var ResultCode: Integer;

// On upgrade: silently uninstall the previous version first so no stale files remain
procedure CurStepChanged(CurStep: TSetupStep);
var
  UninstPath: string;
  UninstExe:  string;
begin
  if CurStep = ssInstall then begin
    // Plain string assignment — do NOT wrap in ExpandConstant() or Inno will
    // try to interpret the GUID braces as a constant name and throw an error.
    UninstPath := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' +
                  '{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}_is1';
    if RegQueryStringValue(HKLM, UninstPath, 'UninstallString', UninstExe) or
       RegQueryStringValue(HKCU, UninstPath, 'UninstallString', UninstExe) then begin
      UninstExe := RemoveQuotes(UninstExe);
      if FileExists(UninstExe) then
        Exec(UninstExe, '/SILENT /NORESTART', '', SW_HIDE,
             ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

// Kill any running VajraStocks process before uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM VajraStocks.exe',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
