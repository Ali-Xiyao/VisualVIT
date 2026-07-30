param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("A2", "A3", "A4", "A5", "A6_no_state", "A6")]
    [string]$Variant,

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
$OutputRoot = Join-Path $R40Root "components\$Variant\seed_$Seed"
$SafeVariant = $Variant.ToLowerInvariant()
$StatusPath = Join-Path $R40Root "r40_${SafeVariant}_seed_${Seed}_status.json"
$StdoutPath = Join-Path $R40Root "r40_${SafeVariant}_seed_${Seed}.stdout.log"
$StderrPath = Join-Path $R40Root "r40_${SafeVariant}_seed_${Seed}.stderr.log"
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
if (Test-Path -LiteralPath $OutputRoot) {
    throw "R40 component output must be fresh: $OutputRoot"
}
if (Test-Path -LiteralPath $StatusPath) {
    throw "R40 component status must be fresh: $StatusPath"
}
if (Test-Path -LiteralPath $StdoutPath) {
    throw "R40 component stdout must be fresh: $StdoutPath"
}
if (Test-Path -LiteralPath $StderrPath) {
    throw "R40 component stderr must be fresh: $StderrPath"
}

$Existing = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "run_r37_prta_smoke.py" -and
        $_.CommandLine -match "--r40-component" -and
        $_.CommandLine -match "--variant\s+$Variant(\s|$)" -and
        $_.CommandLine -match "--seed\s+$Seed(\s|$)"
    }
if ($Existing) {
    throw "Duplicate R40 $Variant Seed $Seed process detected"
}

$Status = @{
    schema = "visualvit.r40.component-seed-launch.v1"
    status = "RUNNING_R40_COMPONENT_SEED"
    protocol_id = "r40-component-baseline-v1"
    variant = $Variant
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
    "scripts/run_r37_prta_smoke.py",
    "--r40-component",
    "--config", $ConfigPath,
    "--variant", $Variant,
    "--seed", "$Seed",
    "--device", $Device,
    "--transition-root", $TransitionRoot,
    "--cache-root", (Join-Path $Runtime "r37_block8_token_cache"),
    "--text-cache", (Join-Path $Runtime "r37_biomedclip_text_embeddings.pt"),
    "--cmcp-index", (Join-Path $Runtime "r37_counterfactual_prior_index.json"),
    "--output-root", $OutputRoot,
    "--max-train-examples", "0",
    "--max-calibration-examples", "0",
    "--epochs", "3",
    "--batch-size", "2",
    "--learning-rate", "0.0001",
    "--adapter-rank", "32"
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
        $Result.schema -eq "visualvit.r40.component-formal-training.v1" -and
        $Result.status -eq "PASS_R40_COMPONENT_FORMAL_TRAINING" -and
        $Result.protocol_id -eq "r40-component-baseline-v1" -and
        $Result.variant -eq $Variant -and
        $Result.seed -eq $Seed -and
        $Result.formal -eq $true -and
        $Result.r40_component -eq $true -and
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
    "PASS_R40_COMPONENT_SEED"
}
else {
    "STOP_R40_COMPONENT_SEED_ENGINEERING"
}
$Status.pid = $null
$Status.process_exit_code = $ProcessExitCode
$Status.result_complete = $Complete
Write-Status -Payload $Status

if (-not $Complete) {
    exit 2
}
