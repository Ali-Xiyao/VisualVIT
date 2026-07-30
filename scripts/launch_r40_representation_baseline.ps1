param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("B0_frozen_a0", "B2_siamese_signed_abs")]
    [string]$Baseline,

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
$R40Root = Join-Path $Runtime "r40_outcome_independent_v1"
$TransitionRoot = Join-Path $R40Root "transitions"
$OutputRoot = Join-Path $R40Root "baselines\$Baseline\seed_$Seed"
$SafeBaseline = $Baseline.ToLowerInvariant()
$StatusPath = Join-Path $R40Root "r40_${SafeBaseline}_seed_${Seed}_status.json"
$StdoutPath = Join-Path $R40Root "r40_${SafeBaseline}_seed_${Seed}.stdout.log"
$StderrPath = Join-Path $R40Root "r40_${SafeBaseline}_seed_${Seed}.stderr.log"
$ConfigPath = Join-Path $Workspace "configs\r40\r40_component_and_baseline_v1.json"
$Python = (Get-Command python -ErrorAction Stop).Source

function Write-Status {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Payload
    )
    $Temporary = "$StatusPath.tmp"
    $Payload.updated_at = (Get-Date).ToString("o")
    $Payload | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $Temporary -Encoding UTF8
    Move-Item -LiteralPath $Temporary -Destination $StatusPath -Force
}

if (-not (Test-Path -LiteralPath $TransitionRoot)) {
    throw "R40 transition roster is missing: $TransitionRoot"
}
foreach ($Path in @($OutputRoot, $StatusPath, $StdoutPath, $StderrPath)) {
    if (Test-Path -LiteralPath $Path) {
        throw "R40 representation baseline path must be fresh: $Path"
    }
}
$Existing = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "run_r40_representation_baseline.py" -and
        $_.CommandLine -match "--baseline\s+$Baseline(\s|$)" -and
        $_.CommandLine -match "--seed\s+$Seed(\s|$)"
    }
if ($Existing) {
    throw "Duplicate R40 $Baseline Seed $Seed process detected"
}

$Status = @{
    schema = "visualvit.r40.representation-baseline-launch.v1"
    status = "RUNNING_R40_REPRESENTATION_BASELINE"
    protocol_id = "r40-component-baseline-v1"
    baseline = $Baseline
    seed = $Seed
    device = $Device
    pid = $PID
    output_root = $OutputRoot
    stdout_log = $StdoutPath
    stderr_log = $StderrPath
    protected_300_dev_read = $false
    revealed_483_test_read = $false
    gold_outcomes_read = $false
    source_hashes_recomputed = $false
    per_shard_hashes_computed = $false
    checkpoint_hashes_recomputed = $false
    scientific_claim_allowed = $false
}
Write-Status -Payload $Status

$Arguments = @(
    "scripts/run_r40_representation_baseline.py",
    "--config", $ConfigPath,
    "--baseline", $Baseline,
    "--seed", "$Seed",
    "--device", $Device,
    "--transition-root", $TransitionRoot,
    "--cache-root", (Join-Path $Runtime "r37_block8_token_cache"),
    "--text-cache", (Join-Path $Runtime "r37_biomedclip_text_embeddings.pt"),
    "--output-root", $OutputRoot,
    "--max-train-examples", "0",
    "--max-development-examples", "0",
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
        $Result.schema -eq "visualvit.r40.representation-baseline-seed.v1" -and
        $Result.status -eq "PASS_R40_REPRESENTATION_BASELINE_SEED" -and
        $Result.protocol_id -eq "r40-component-baseline-v1" -and
        $Result.baseline -eq $Baseline -and
        $Result.seed -eq $Seed -and
        $Result.formal -eq $true -and
        $Result.protected_300_dev_read -eq $false -and
        $Result.revealed_483_test_read -eq $false -and
        $Result.gold_outcomes_read -eq $false -and
        $Result.source_hashes_recomputed -eq $false -and
        $Result.per_shard_hashes_computed -eq $false -and
        $Result.checkpoint_hashes_recomputed -eq $false -and
        $Result.scientific_claim_allowed -eq $false
    )
}

$Status.status = if ($Complete) {
    "PASS_R40_REPRESENTATION_BASELINE"
}
else {
    "STOP_R40_REPRESENTATION_BASELINE_ENGINEERING"
}
$Status.pid = $null
$Status.process_exit_code = $ProcessExitCode
$Status.result_complete = $Complete
Write-Status -Payload $Status

if (-not $Complete) {
    exit 2
}
