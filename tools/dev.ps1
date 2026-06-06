param(
  [Parameter(Position = 0)]
  [ValidateSet("check", "doctor", "logs", "run", "ui", "calibration", "switch-proxima", "switch-yung", "switch-old", "ai-preflight", "ai-postedit", "ai-logscan")]
  [string]$Command = "check",

  [int]$Tail = 120
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

function Ensure-Python {
  if (-not (Test-Path $Python)) {
    py -3 -m venv (Join-Path $Root ".venv")
  }
  & $Python -m pip install -r (Join-Path $Root "requirements.txt")
}

function Invoke-Check {
  Ensure-Python
  Push-Location $Root
  try {
    & $Python -m compileall coc_bot
    & $Python -c "from coc_bot.config import load_config, validate_config; c=load_config(); validate_config(c); print('config ok'); print('fallback_deploy_points=', len(c.fallback_deploy_points)); print('deploy_step_delay_seconds=', c.deploy_step_delay_seconds); print('rapid_deploy_tap_delay_seconds=', c.rapid_deploy_tap_delay_seconds); print('dry_run=', c.dry_run); print('log_level=', c.log_level)"
  } finally {
    Pop-Location
  }
}

function Invoke-Doctor {
  Ensure-Python
  Push-Location $Root
  try {
    & $Python -c "from coc_bot.config import load_config; c=load_config(); print('adb_path=', c.adb_path); print('ldplayer=', c.ldplayer_player_path); print('serial=', c.device_serial); print('package=', c.package_name)"
    & $Python -c "from coc_bot.config import load_config; from coc_bot.adb_device import AdbDevice; c=load_config(); d=AdbDevice(c.adb_path,c.device_serial,c.dry_run); print(d.host_run('devices').stdout.strip()); d.connect(); d.check(); print('screen_size=', d.screen_size()); raw=d.screenshot(); print('screenshot_bytes=', len(raw))"
    & $Python -c "from coc_bot.config import load_config; from coc_bot.adb_device import AdbDevice; from coc_bot.vision import VisionModule; c=load_config(); d=AdbDevice(c.adb_path,c.device_serial,c.dry_run); v=VisionModule(d,c); print('state=', v.detect_state())"
  } finally {
    Pop-Location
  }
}

function Show-Logs {
  $Log = Join-Path $Root "logs\bot.log"
  if (-not (Test-Path $Log)) {
    Write-Host "No log found: $Log"
    return
  }
  Get-Content $Log -Tail $Tail
  Write-Host ""
  Write-Host "Recent warnings/errors:"
  Select-String -Path $Log -Pattern "ERROR|WARNING|Traceback|RuntimeError|failed|Unable|not detected|cv2.error|ADB" -CaseSensitive:$false |
    Select-Object -Last 40
}

switch ($Command) {
  "check" { Invoke-Check }
  "doctor" { Invoke-Doctor }
  "logs" { Show-Logs }
  "run" {
    Ensure-Python
    Push-Location $Root
    try { & $Python -m coc_bot.main } finally { Pop-Location }
  }
  "ui" {
    Ensure-Python
    Push-Location $Root
    try { & $Python -m coc_bot.ui } finally { Pop-Location }
  }
  "calibration" {
    Ensure-Python
    Push-Location $Root
    try {
      & $Python -c "from coc_bot.config import load_config; from coc_bot.adb_device import AdbDevice; from coc_bot.vision import VisionModule; from coc_bot.calibration import CalibrationOverlay; c=load_config(); d=AdbDevice(c.adb_path,c.device_serial,c.dry_run); d.connect(); d.check(); v=VisionModule(d,c); path=CalibrationOverlay(c).save_overlay(v.screenshot_array(), c.calibration_overlay_dir, 'manual'); print(path)"
    } finally {
      Pop-Location
    }
  }
  "switch-proxima" {
    Ensure-Python
    Push-Location $Root
    try { & $Python -m coc_bot.account proxima } finally { Pop-Location }
  }
  "switch-yung" {
    Ensure-Python
    Push-Location $Root
    try { & $Python -m coc_bot.account yung_proxima } finally { Pop-Location }
  }
  "switch-old" {
    Ensure-Python
    Push-Location $Root
    try { & $Python -m coc_bot.account old_proxima } finally { Pop-Location }
  }
  "ai-preflight" {
    Write-Host "AI preflight: project state"
    Write-Host "Root: $Root"
    Write-Host "Active config: " -NoNewline
    if (Test-Path (Join-Path $Root "config.json")) { Write-Host "config.json" } else { Write-Host "config.example.json" }
    Invoke-Check
  }
  "ai-postedit" {
    Write-Host "AI post-edit validation"
    Invoke-Check
  }
  "ai-logscan" {
    Show-Logs
  }
}
