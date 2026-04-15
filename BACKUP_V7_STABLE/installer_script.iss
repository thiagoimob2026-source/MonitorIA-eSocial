; Script IA_eSocial
[Setup]
AppName=IA_eSocial Monitor
AppVersion=1.5
DefaultDirName={autopf}\IA_eSocial
DefaultGroupName=IA_eSocial
OutputDir=.
OutputBaseFilename=Setup_IA_eSocial
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; IMPORTANTE: Certifique-se de que o arquivo abaixo existe na pasta dist antes de compilar
Source: "dist\IA_eSocial.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\IA_eSocial"; Filename: "{app}\IA_eSocial.exe"
Name: "{commondesktop}\IA_eSocial"; Filename: "{app}\IA_eSocial.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\IA_eSocial.exe"; Description: "{cm:LaunchProgram,IA_eSocial}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Messages]
brazilianportuguese.WelcomeLabel2=Este programa gerencia a transmissão de eventos do eSocial através do ACBrMonitor.%n%nCertifique-se de ter o Certificado A3 conectado e o ACBrMonitor instalado.
