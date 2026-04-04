# APO Installation and Rollback Plan

This flow requires admin rights, code signing, and test endpoint hardware IDs.

## Build prerequisites
- Visual Studio with Windows Driver Kit (WDK)
- Test certificate trusted in local machine
- Administrator PowerShell

## High-level installation
1. Build APO DLL and COM registration package.
2. Sign DLL with test or production certificate.
3. Register COM class and endpoint effect metadata.
4. Attach APO CLSID to target endpoint FX chain.
5. Restart Windows Audio service.

## Sample command skeleton
```powershell
# Placeholder: replace with your built binaries and CLSID values.
reg add "HKLM\SOFTWARE\Classes\CLSID\{YOUR-APO-CLSID}" /ve /d "BossForge Endpoint APO" /f
reg add "HKLM\SOFTWARE\Classes\CLSID\{YOUR-APO-CLSID}\InprocServer32" /ve /d "C:\Program Files\BossForge\BossForgeApo.dll" /f
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Audio\Plugins\Fx\{YOUR-APO-CLSID}" /ve /d "BossForge Endpoint APO" /f
Restart-Service Audiosrv -Force
```

## Rollback
```powershell
Restart-Service Audiosrv -Force
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Audio\Plugins\Fx\{YOUR-APO-CLSID}" /f
reg delete "HKLM\SOFTWARE\Classes\CLSID\{YOUR-APO-CLSID}" /f
Restart-Service Audiosrv -Force
```

## Safety notes
- Export affected registry keys before changes.
- Keep a signed baseline installer for quick repair.
- Validate APO only on non-production endpoints before broad rollout.
