; Inno Setup script for VajraStocks Windows installer
; Produces: VajraStocks-Setup.exe
; Requires: PyInstaller onedir output at ..\..\dist\VajraStocks\
;
; Called by GitHub Actions with  APP_VERSION  set in the environment:
;   ISCC /Q setup.iss
; Or locally:
;   set APP_VERSION=1.0.0 && ISCC setup.iss

#define AppName      "VajraStocks"
#define AppPublisher "Abhishek"
#define AppURL       "https://github.com/abhishek4official/VajraStocks"
#define AppExeName   "VajraStocks.exe"
#define SrcDir       "..\..\dist\VajraStocks"
#define IconFile     "..\assets\icon.ico"

; Use APP_VERSION env var; fall back to "1.0.0" if not set
#define AppVersion GetEnv("APP_VERSION")
#if AppVersion == ""
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Only set SetupIconFile if the icon actually exists — avoids compile error
#if FileExists(IconFile)
SetupIconFile={#IconFile}
#endif
OutputDir=..\..\release
OutputBaseFilename=VajraStocks-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start VajraStocks automatically at Windows login"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; Auto-start: written only when user selects the startup task
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the user-data folder created at runtime (db, logs)
Type: filesandordirs; Name: "{app}\data"

[Code]
var ResultCode: Integer;

// Kill any running VajraStocks process before uninstall proceeds
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM VajraStocks.exe',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
