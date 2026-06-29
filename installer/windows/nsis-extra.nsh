; Custom NSIS script — runs before the installer copies any files.
; Kills any running VajraStocks process so the installer can overwrite
; the exe without "file in use" errors.

!macro customInstall
  DetailPrint "Stopping any running VajraStocks instance..."
  ; /F = force, /T = terminate child tree, /IM = by image name
  ; Suppress errors — if the process is not running this exits with code 128
  ExecWait 'taskkill /F /T /IM "VajraStocks.exe"'
  ; Brief pause so Windows releases file handles
  Sleep 1000
!macroend

!macro customUnInstall
  DetailPrint "Stopping VajraStocks before uninstall..."
  ExecWait 'taskkill /F /T /IM "VajraStocks.exe"'
  Sleep 500
!macroend
