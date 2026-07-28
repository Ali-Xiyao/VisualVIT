param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(17, 29, 43)]
    [int]$Seed,

    [Parameter(Mandatory = $true)]
    [ValidateSet("cuda:0", "cuda:1")]
    [string]$Device
)

$ErrorActionPreference = "Stop"

$Workspace = "E:\Xiyaowang\050_VisualVIT"
$Runtime = "H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
$OutputRoot = Join-Path $Runtime "r37_1_formal\a0_v1\seed_$Seed"
$StatusPath = Join-Path $Runtime "r37_1_a0_seed_${Seed}_status.json"
$StdoutPath = Join-Path $Runtime "r37_1_a0_seed_${Seed}.stdout.log"
$StderrPath = Join-Path $Runtime "r37_1_a0_seed_${Seed}.stderr.log"
$Python = (Get-Command python -ErrorAction Stop).Source

function Write-Status {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Payload
    )
    $Temporary = "$StatusPath.tmp"
    $Payload.updated_at = (Get-Date).ToString("o")
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Temporary -Encoding UTF8
    Move-Item -LiteralPath $Temporary -Destination $StatusPath -Force
}

if (Test-Path -LiteralPath $OutputRoot) {
    throw "R37.1 A0 seed output must be fresh: $OutputRoot"
}
if (Test-Path -LiteralPath $StdoutPath) {
    throw "R37.1 A0 stdout log must be fresh: $StdoutPath"
}
if (Test-Path -LiteralPath $StderrPath) {
    throw "R37.1 A0 stderr log must be fresh: $StderrPath"
}

$Existing = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "run_r37_a0_frozen_probe.py" -and
        $_.CommandLine -match "--r37-1" -and
        $_.CommandLine -match "--seed\s+$Seed(\s|$)"
    }
if ($Existing) {
    throw "Duplicate R37.1 A0 seed process detected for seed $Seed"
}

$Status = @{
    schema = "visualvit.r37-1.a0-seed-launch.v1"
    status = "RUNNING_R37_1_A0_FORMAL_SEED"
    variant = "A0"
    seed = $Seed
    device = $Device
    pid = $PID
    output_root = $OutputRoot
    stdout_log = $StdoutPath
    stderr_log = $StderrPath
    protected_outcomes_read = $false
    sealed_test_read = $false
    gold_outcomes_read = $false
    source_hashes_recomputed = $false
    per_shard_hashes_computed = $false
    scientific_claim_allowed = $false
}
Write-Status -Payload $Status

$Arguments = @(
    "scripts/run_r37_a0_frozen_probe.py",
    "--r37-1",
    "--seed", "$Seed",
    "--device", $Device,
    "--transition-root", (Join-Path $Runtime "r37_1_transitions_v1"),
    "--cache-root", (Join-Path $Runtime "r37_block8_token_cache"),
    "--text-cache", (Join-Path $Runtime "r37_biomedclip_text_embeddings.pt"),
    "--output-root", $OutputRoot,
    "--max-train-examples", "0",
    "--max-calibration-examples", "0",
    "--epochs", "100",
    "--batch-size", "16",
    "--learning-rate", "0.01"
)

try {
    Push-Location $Workspace
    & $Python @Arguments 1> $StdoutPath 2> $StderrPath
    $ProcessExitCode = $LASTEXITCODE
}
catch {
    $ProcessExitCode = 1
    $_ | Out-String | Add-Content -LiteralPath $StderrPath -Encoding UTF8
}
finally {
    Pop-Location
}

$ResultPath = Join-Path $OutputRoot "result.json"
$CheckpointPath = Join-Path $OutputRoot "checkpoint.pt"
$Complete = $false
if (
    $ProcessExitCode -eq 0 -and
    (Test-Path -LiteralPath $ResultPath) -and
    (Test-Path -LiteralPath $CheckpointPath)
) {
    $Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
    $Complete = (
        $Result.schema -eq "visualvit.r37-1.a0-formal-probe.v1" -and
        $Result.status -eq "PASS_R37_1_A0_FORMAL_PROBE" -and
        $Result.variant -eq "A0" -and
        $Result.seed -eq $Seed -and
        $Result.formal -eq $true -and
        $Result.r37_1 -eq $true -and
        $Result.protected_outcomes_read -eq $false -and
        $Result.sealed_test_read -eq $false -and
        $Result.gold_outcomes_read -eq $false -and
        $Result.source_hashes_recomputed -eq $false -and
        $Result.scientific_claim_allowed -eq $false
    )
}

$Status.status = if ($Complete) {
    "PASS_R37_1_A0_FORMAL_SEED"
}
else {
    "STOP_R37_1_A0_FORMAL_SEED_ENGINEERING"
}
$Status.pid = $null
$Status.process_exit_code = $ProcessExitCode
$Status.result_complete = $Complete
Write-Status -Payload $Status

if (-not $Complete) {
    exit 2
}
