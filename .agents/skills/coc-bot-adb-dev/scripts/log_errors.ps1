param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path,
  [int]$Last = 80
)

$log = Join-Path $Root "logs\bot.log"
if (-not (Test-Path $log)) {
  Write-Host "No log found: $log"
  exit 0
}

Select-String -Path $log -Pattern "ERROR|WARNING|Traceback|RuntimeError|failed|Unable|not detected|cv2.error|ADB" -CaseSensitive:$false |
  Select-Object -Last $Last
