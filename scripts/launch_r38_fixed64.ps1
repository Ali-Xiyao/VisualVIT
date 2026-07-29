param(
    [string]$Python = "python",
    [string]$Config = "configs\r38\r38_fixed64_survival_v1.json"
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Runtime = "H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
$OutputRoot = Join-Path $Runtime "r38_fixed64_survival_v1"
$StatusPath = Join-Path $Runtime "r38_pipeline_status.json"
$LogRoot = Join-Path $Runtime "r38_pipeline_logs"

function Write-Status {
    param([string]$Status, [string]$Stage, [hashtable]$Extra = @{})
    $payload = @{
        schema = "visualvit.r38.pipeline-status.v1"
        status = $Status
        stage = $Stage
        config = $Config
        updated_at = (Get-Date).ToString("o")
        protected_300_dev_read = $true
        sealed_483_test_read = $false
        gold_outcomes_read = $false
        source_hashes_recomputed = $false
        per_shard_hashes_computed = $false
        checkpoint_hashes_recomputed = $false
    }
    foreach ($key in $Extra.Keys) { $payload[$key] = $Extra[$key] }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatusPath -Encoding utf8
}

function Start-Seed {
    param([int]$Seed, [string]$Device)
    $name = "seed_$Seed"
    $process = Start-Process -FilePath $Python -ArgumentList @(
        "scripts\run_r38_fixed64_seed.py",
        "--config", $Config,
        "--seed", "$Seed",
        "--device", $Device
    ) -WorkingDirectory $Repo -WindowStyle Hidden `
      -RedirectStandardOutput (Join-Path $LogRoot "$name.stdout.log") `
      -RedirectStandardError (Join-Path $LogRoot "$name.stderr.log") `
      -PassThru
    return @{ Name = $name; Seed = $Seed; Device = $Device; Process = $process }
}

function Wait-Seed {
    param([hashtable]$Job)
    $Job.Process.WaitForExit()
    if (
        $null -ne $Job.Process.ExitCode -and
        [int]$Job.Process.ExitCode -ne 0
    ) {
        throw "$($Job.Name) failed with exit code $($Job.Process.ExitCode)"
    }
    $result = Join-Path $OutputRoot "$($Job.Name)\result.json"
    if (-not (Test-Path -LiteralPath $result -PathType Leaf)) {
        throw "$($Job.Name) ended without a complete result"
    }
}

if (Test-Path -LiteralPath $StatusPath) {
    throw "R38 status already exists; refusing duplicate launch"
}
if (Test-Path -LiteralPath $OutputRoot) {
    throw "R38 output already exists; refusing non-fresh launch"
}
New-Item -ItemType Directory -Path $LogRoot -ErrorAction Stop | Out-Null

try {
    $jobs = @(
        (Start-Seed -Seed 17 -Device "cuda:0"),
        (Start-Seed -Seed 29 -Device "cuda:1")
    )
    Write-Status -Status "RUNNING_R38" -Stage "seed_17_29" -Extra @{
        jobs = @(
            $jobs | ForEach-Object {
                @{ name = $_.Name; pid = $_.Process.Id; device = $_.Device }
            }
        )
    }
    foreach ($job in $jobs) { Wait-Seed -Job $job }

    $seed43 = Start-Seed -Seed 43 -Device "cuda:0"
    Write-Status -Status "RUNNING_R38" -Stage "seed_43" -Extra @{
        jobs = @(
            @{ name = $seed43.Name; pid = $seed43.Process.Id; device = $seed43.Device }
        )
    }
    Wait-Seed -Job $seed43

    Write-Status -Status "RUNNING_R38" -Stage "aggregate"
    $aggregate = Start-Process -FilePath $Python -ArgumentList @(
        "scripts\aggregate_r38_fixed64.py",
        "--config", $Config
    ) -WorkingDirectory $Repo -WindowStyle Hidden `
      -RedirectStandardOutput (Join-Path $LogRoot "aggregate.stdout.log") `
      -RedirectStandardError (Join-Path $LogRoot "aggregate.stderr.log") `
      -PassThru
    $aggregate.WaitForExit()
    $qualificationPath = Join-Path $OutputRoot "qualification.json"
    if (-not (Test-Path -LiteralPath $qualificationPath -PathType Leaf)) {
        throw "R38 aggregate ended without qualification"
    }
    $qualification = Get-Content -LiteralPath $qualificationPath -Raw | ConvertFrom-Json
    Write-Status -Status $qualification.status -Stage "complete" -Extra @{
        scientific_go = [bool]$qualification.scientific_go
        aggregate_exit_code = $aggregate.ExitCode
    }
    if ([bool]$qualification.scientific_go) { exit 0 }
    exit 2
}
catch {
    Write-Status -Status "STOP_R38_ENGINEERING" -Stage "failed" -Extra @{
        error = $_.Exception.Message
    }
    throw
}
