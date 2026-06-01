; Inno Setup 脚本 — Voice Input Windows 安装包
; 由 CI 调用: ISCC /DMyAppVersion=0.1.0 installer\windows\voice-input.iss
; 产物: installer\windows\Output\voice-input-<版本>-setup.exe
;
; 安装策略：装到当前用户目录（免管理员），模型首次运行自行下载。

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#define MyAppName "Voice Input"
#define MyAppPublisher "fnidore"
#define MyAppExeName "voice-input.exe"
#define MyAppURL "https://github.com/fnidore/voice-input"

[Setup]
; 固定 AppId（升级时识别同一程序，切勿改动）
AppId={{B7E4F2A1-9C3D-4E5B-8A6F-1D2C3B4A5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
; 免管理员：装到 {localappdata}\Programs\VoiceInput
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\VoiceInput
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=voice-input-{#MyAppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
; 注：GitHub runner 的 Inno Setup 默认只带英文 Default.isl，
; 简体中文 ChineseSimplified.isl 属附加语言、运行器上不存在，故向导用英文。
; （程序界面本身全中文，不受向导语言影响）
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "开机自动启动 Voice Input"; GroupDescription: "启动选项:"; Flags: unchecked

[Files]
; PyInstaller onedir 产物整目录打入（相对本脚本：仓库根 dist\voice-input\）
Source: "..\..\dist\voice-input\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; 开机自启（写当前用户 Run 键，免管理员）
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "VoiceInput"; ValueData: """{app}\{#MyAppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    Flags: nowait postinstall skipifsilent
