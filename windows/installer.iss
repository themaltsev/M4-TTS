#define AppName "Selected Text Speech"
#define AppVersion "1.0.0"
#define AppExe "selected-text-speech.exe"

[Setup]
AppId={{90C85A27-B6BB-4FD1-BB7E-6D9A1B711FAB}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=themaltsev
DefaultDirName={localappdata}\SelectedTextSpeech
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\dist
OutputBaseFilename=install-windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Dirs]
Name: "{userappdata}\selected-text-speech"

[Files]
Source: "..\dist\selected-text-speech.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "run-tray.vbs"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Selected Text Speech"; Filename: "{app}\run-tray.vbs"; Parameters: """{app}\{#AppExe}"""; WorkingDir: "{app}"

[Run]
Filename: "{app}\run-tray.vbs"; Parameters: """{app}\{#AppExe}"""; Flags: skipifsilent nowait

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /T /IM {#AppExe}"; Flags: runhidden waituntilterminated; RunOnceId: "StopSelectedTextSpeech"

[Code]
var
  RemoveUserConfig: Boolean;

procedure InitializeWizard;
begin
  RemoveUserConfig := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath, DefaultConfig, StartupLink, ShortcutParameters: String;
  ExistingConfig: AnsiString;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigPath := ExpandConstant('{userappdata}\selected-text-speech\config.env');
    DefaultConfig :=
      'EDGE_TTS_VOICE=ru-RU-SvetlanaNeural'#13#10 +
      'EDGE_TTS_RATE=+0%'#13#10 +
      'EDGE_TTS_VOLUME=+0%'#13#10 +
      'EDGE_TTS_PITCH=+0Hz'#13#10 +
      'MPV_PLAYBACK_VOLUME=100'#13#10 +
      'API_MAX_ATTEMPTS=3'#13#10 +
      'API_RETRY_BASE_SECONDS=1.5'#13#10 +
      'API_RETRY_MAX_SECONDS=8'#13#10 +
      'HOTKEY=ctrl+alt+s'#13#10;
    if not FileExists(ConfigPath) then
      SaveStringToFile(ConfigPath, DefaultConfig, False)
    else if LoadStringFromFile(ConfigPath, ExistingConfig) and
      (Pos('HOTKEY=', Uppercase(String(ExistingConfig))) = 0) then
      SaveStringToFile(ConfigPath, #13#10 + 'HOTKEY=ctrl+alt+s'#13#10, True);

    if not WizardSilent then
    begin
      StartupLink := ExpandConstant('{userstartup}\Selected Text Speech.lnk');
      if MsgBox('Добавить Selected Text Speech в автозапуск при входе в Windows?',
        mbConfirmation, MB_YESNO) = IDYES then
      begin
        ShortcutParameters := ExpandConstant('"{app}\run-tray.vbs" "{app}\{#AppExe}"');
        CreateShellLink(StartupLink, 'Selected Text Speech',
          ExpandConstant('{sys}\wscript.exe'), ShortcutParameters,
          ExpandConstant('{app}'), '', 0, SW_SHOWNORMAL);
      end
      else
        DeleteFile(StartupLink);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveUserConfig := MsgBox('Удалить пользовательские настройки и голос вместе с программой?',
      mbConfirmation, MB_YESNO) = IDYES;
  if (CurUninstallStep = usPostUninstall) and RemoveUserConfig then
    DelTree(ExpandConstant('{userappdata}\selected-text-speech'), True, True, True);
end;
