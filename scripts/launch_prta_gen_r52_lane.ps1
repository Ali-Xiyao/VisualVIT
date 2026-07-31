param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('lane0', 'lane1')]
  [string]$Lane
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$config = Join-Path $workspace 'configs\prta_gen\prta_gen_r52_matched_direct_head_v1.json'
$python = (Get-Command python).Source
$spec = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
$device = if ($Lane -eq 'lane0') { 'cuda:0' } else { 'cuda:1' }
$jobs = $spec.execution.$Lane

foreach ($job in $jobs) {
  if ($job -notmatch '^(prta_exact64|tila_exact64|b2_exact64)_seed(17|29|43)$') {
    throw "Unregistered R52 lane job: $job"
  }
  $arm = $Matches[1]
  $seed = [int]$Matches[2]
  & $python (Join-Path $workspace 'scripts\run_prta_gen_r52_matched_direct_head.py') `
    --config $config --arm $arm --seed $seed --device $device
  if ($LASTEXITCODE -ne 0) {
    throw "R52 lane stopped at $arm seed $seed"
  }
}
