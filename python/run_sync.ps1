# PowerShell Scheduled Task Execution Runner for NSE Historical Stock Data Downloader

# Absolute path resolution
$ProjectDir = $PSScriptRoot
$LogFile = Join-Path $ProjectDir "logs\powershell_runner.log"
$ConfigPath = Join-Path $ProjectDir "config\config.yaml"

# Ensure logs folder exists
New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null

$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$Timestamp] PowerShell scheduled task runner triggered." | Out-File -FilePath $LogFile -Append

# Set execution directory to project root (Task Scheduler defaults to System32)
Set-Location -Path $ProjectDir

try {
    # Run the downloader CLI via UV
    & uv run nse-downloader sync --config-path "$ConfigPath" 2>&1 | Out-File -FilePath $LogFile -Append
    
    $EndTimestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$EndTimestamp] Downloader sync execution completed successfully." | Out-File -FilePath $LogFile -Append
} catch {
    $ErrorTimestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$ErrorTimestamp] CRITICAL ERROR: Execution failed. Details: $_" | Out-File -FilePath $LogFile -Append
    exit 1
}
