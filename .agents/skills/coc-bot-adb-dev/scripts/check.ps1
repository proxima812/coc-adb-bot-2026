param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
)

$ErrorActionPreference = "Stop"
Push-Location $Root
try {
  & ".\.venv\Scripts\python.exe" -m compileall coc_bot
  & ".\.venv\Scripts\python.exe" -c "from coc_bot.config import load_config; c=load_config(); print('config ok', len(c.fallback_deploy_points), c.deploy_step_delay_seconds, c.rapid_deploy_tap_delay_seconds)"
} finally {
  Pop-Location
}
