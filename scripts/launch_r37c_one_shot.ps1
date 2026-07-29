param(
    [string]$Python = "python",
    [string]$Candidate = "configs\r37\r37_1_candidate_for_r37c_v1.json"
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Runtime = "H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
$StatusPath = Join-Path $Runtime "r37c_pipeline_status.json"
$LogRoot = Join-Path $Runtime "r37c_pipeline_logs"
$ProtectedRead = $false

function Write-Status {
    param(
        [string]$Status,
        [string]$Stage,
        [hashtable]$Extra = @{}
    )
    $payload = @{
        schema = "visualvit.r37c.pipeline-status.v1"
        status = $Status
        stage = $Stage
        candidate = $Candidate
        updated_at = (Get-Date).ToString("o")
        protected_300_dev_read = $ProtectedRead
        sealed_483_test_read = $false
        gold_outcomes_read = $false
        source_hashes_recomputed = $false
        per_shard_hashes_computed = $false
    }
    foreach ($key in $Extra.Keys) {
        $payload[$key] = $Extra[$key]
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatusPath -Encoding utf8
}

function Invoke-PythonStage {
    param(
        [string]$Name,
        [string[]]$Arguments
    )
    $stdout = Join-Path $LogRoot "$Name.stdout.log"
    $stderr = Join-Path $LogRoot "$Name.stderr.log"
    $process = Start-Process -FilePath $Python `
        -ArgumentList $Arguments `
        -WorkingDirectory $Repo `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -WindowStyle Hidden `
        -PassThru
    $process.WaitForExit()
    if ($null -ne $process.ExitCode -and [int]$process.ExitCode -ne 0) {
        throw "$Name failed with exit code $($process.ExitCode)"
    }
}

if (Test-Path -LiteralPath $StatusPath) {
    throw "R37C pipeline status already exists; refusing duplicate launch: $StatusPath"
}
New-Item -ItemType Directory -Path $LogRoot -ErrorAction Stop | Out-Null

try {
    Write-Status -Status "RUNNING_R37C" -Stage "cache"
    Invoke-PythonStage -Name "cache" -Arguments @(
        "scripts\prepare_r37c_dev_cache.py",
        "--candidate", $Candidate,
        "--device", "cuda:0"
    )

    Write-Status -Status "RUNNING_R37C" -Stage "reveal"
    Invoke-PythonStage -Name "reveal" -Arguments @(
        "scripts\reveal_r37c_dev_labels.py",
        "--candidate", $Candidate
    )
    $ProtectedRead = $true

    Write-Status -Status "RUNNING_R37C" -Stage "seed_17_29"
    $jobs = @()
    foreach ($entry in @(
        @{ Seed = 17; Device = "cuda:0" },
        @{ Seed = 29; Device = "cuda:1" }
    )) {
        $name = "seed_$($entry.Seed)"
        $stdout = Join-Path $LogRoot "$name.stdout.log"
        $stderr = Join-Path $LogRoot "$name.stderr.log"
        $arguments = @(
            "scripts\run_r37c_seed_eval.py",
            "--candidate", $Candidate,
            "--seed", "$($entry.Seed)",
            "--device", $entry.Device
        )
        $process = Start-Process -FilePath $Python `
            -ArgumentList $arguments `
            -WorkingDirectory $Repo `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -WindowStyle Hidden `
            -PassThru
        $jobs += @{ Name = $name; Process = $process; Device = $entry.Device }
    }
    Write-Status -Status "RUNNING_R37C" -Stage "seed_17_29" -Extra @{
        jobs = @(
            $jobs | ForEach-Object {
                @{
                    name = $_.Name
                    pid = $_.Process.Id
                    device = $_.Device
                }
            }
        )
    }
    foreach ($job in $jobs) {
        $job.Process.WaitForExit()
        if (
            $null -ne $job.Process.ExitCode -and
            [int]$job.Process.ExitCode -ne 0
        ) {
            throw "$($job.Name) failed with exit code $($job.Process.ExitCode)"
        }
        $seed = $job.Name.Replace("seed_", "")
        $result = Join-Path `
            "H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37c_one_shot_dev_v1\evaluations" `
            "seed_$seed\result.json"
        if (-not (Test-Path -LiteralPath $result -PathType Leaf)) {
            throw "$($job.Name) ended without a complete result artifact"
        }
    }

    Write-Status -Status "RUNNING_R37C" -Stage "seed_43"
    Invoke-PythonStage -Name "seed_43" -Arguments @(
        "scripts\run_r37c_seed_eval.py",
        "--candidate", $Candidate,
        "--seed", "43",
        "--device", "cuda:0"
    )

    Write-Status -Status "RUNNING_R37C" -Stage "aggregate"
    $stdout = Join-Path $LogRoot "aggregate.stdout.log"
    $stderr = Join-Path $LogRoot "aggregate.stderr.log"
    $process = Start-Process -FilePath $Python `
        -ArgumentList @(
            "scripts\aggregate_r37c_dev.py",
            "--candidate", $Candidate
        ) `
        -WorkingDirectory $Repo `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -WindowStyle Hidden `
        -PassThru
    $process.WaitForExit()
    $qualification = Get-Content -LiteralPath `
        "H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37c_one_shot_dev_v1\qualification.json" `
        -Raw | ConvertFrom-Json
    Write-Status -Status $qualification.status -Stage "complete" -Extra @{
        scientific_go = [bool]$qualification.scientific_go
        aggregate_exit_code = $process.ExitCode
    }
    if ([bool]$qualification.scientific_go) {
        exit 0
    }
    exit 2
}
catch {
    Write-Status -Status "STOP_R37C_ENGINEERING" -Stage "failed" -Extra @{
        error = $_.Exception.Message
    }
    throw
}
