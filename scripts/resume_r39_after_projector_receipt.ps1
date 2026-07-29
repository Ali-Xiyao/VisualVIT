param(
    [string]$Python = "python",
    [string]$Config = "configs\r39\r39_frozen_vlm_transfer_v1.json"
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Runtime = "H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
$OutputRoot = Join-Path $Runtime "r39_frozen_vlm_transfer_v1"
$StatusPath = Join-Path $Runtime "r39_pipeline_status.json"
$LogRoot = Join-Path $Runtime "r39_pipeline_logs"
$RevealRoot = Join-Path $Runtime "r39_sealed_reveal_v1"
$SealedCache = Join-Path $Runtime "r39_sealed_block8_v1"
$SealedLabelsRead = $false
$LogSuffix = ".receipt1"

function Write-Status {
    param(
        [string]$Status,
        [string]$Stage,
        [hashtable]$Extra = @{}
    )
    $payload = @{
        schema = "visualvit.r39.pipeline-status.v1"
        status = $Status
        stage = $Stage
        config = $Config
        resume = "projector_parameter_receipt_only"
        updated_at = (Get-Date).ToString("o")
        sealed_483_test_labels_read = $SealedLabelsRead
        gold_outcomes_read = $false
        source_hashes_recomputed = $false
        per_shard_hashes_computed = $false
        checkpoint_hashes_recomputed = $false
    }
    foreach ($key in $Extra.Keys) { $payload[$key] = $Extra[$key] }
    $temporary = "$StatusPath.tmp"
    $payload | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination $StatusPath -Force
}

function Start-Stage {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [string]$Device,
        [string]$Expected
    )
    $process = Start-Process -FilePath $Python `
        -ArgumentList $Arguments `
        -WorkingDirectory $Repo `
        -WindowStyle Hidden `
        -RedirectStandardOutput (
            Join-Path $LogRoot "$Name$LogSuffix.stdout.log"
        ) `
        -RedirectStandardError (
            Join-Path $LogRoot "$Name$LogSuffix.stderr.log"
        ) `
        -PassThru
    return @{
        Name = $Name
        Device = $Device
        Expected = $Expected
        Process = $process
    }
}

function Wait-Stage {
    param([hashtable]$Job)
    $Job.Process.WaitForExit()
    $Job.Process.Refresh()
    if ([int]$Job.Process.ExitCode -ne 0) {
        throw "$($Job.Name) failed with exit code $($Job.Process.ExitCode)"
    }
    if (-not (Test-Path -LiteralPath $Job.Expected -PathType Leaf)) {
        throw "$($Job.Name) ended without a complete artifact"
    }
}

function Wait-Group {
    param([hashtable[]]$Jobs)
    Write-Status -Status "RUNNING_R39" -Stage $Jobs[0].Name -Extra @{
        jobs = @(
            $Jobs | ForEach-Object {
                @{
                    name = $_.Name
                    pid = $_.Process.Id
                    device = $_.Device
                    expected = $_.Expected
                }
            }
        )
    }
    foreach ($job in $Jobs) { Wait-Stage -Job $job }
}

function Invoke-SerialStage {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [string]$Expected
    )
    $job = Start-Stage `
        -Name $Name `
        -Arguments $Arguments `
        -Device "cpu" `
        -Expected $Expected
    Wait-Group -Jobs @($job)
}

if (-not (Test-Path -LiteralPath $StatusPath -PathType Leaf)) {
    throw "R39 receipt repair requires the original engineering STOP"
}
$previous = Get-Content -LiteralPath $StatusPath -Raw | ConvertFrom-Json
if (
    $previous.status -ne "STOP_R39_ENGINEERING" -or
    $previous.stage -ne "failed" -or
    $previous.error -notmatch "projector_seed_17 failed"
) {
    throw "R39 receipt repair is allowed only from the registered STOP"
}
if (Test-Path -LiteralPath $RevealRoot) {
    throw "R39 receipt repair refuses any existing sealed reveal"
}
foreach ($seed in @(17, 29, 43)) {
    foreach ($scope in @("dev", "sealed")) {
        $indexPath = Join-Path `
            $OutputRoot `
            "tokens\$scope\seed_$seed\index.json"
        if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) {
            throw "R39 receipt repair cache missing: $indexPath"
        }
        $index = Get-Content -LiteralPath $indexPath -Raw |
            ConvertFrom-Json
        if (
            $index.status -ne "PASS_R39_FIXED64_TOKEN_CACHE" -or
            $index.scope -ne $scope -or
            $index.seed -ne $seed -or
            $index.labels_in_cache -ne $false -or
            $index.sealed_483_test_labels_read -ne $false -or
            $index.gold_outcomes_read -ne $false
        ) {
            throw "R39 receipt repair cache firewall drift: $indexPath"
        }
    }
    foreach ($fresh in @(
        (Join-Path $OutputRoot "projectors\seed_$seed"),
        (Join-Path $OutputRoot "predictions\seed_$seed")
    )) {
        if (Test-Path -LiteralPath $fresh) {
            throw "R39 receipt repair requires fresh downstream output: $fresh"
        }
    }
}
$sealedManifest = Get-Content `
    -LiteralPath (Join-Path $SealedCache "cache_manifest.json") `
    -Raw | ConvertFrom-Json
if (
    $sealedManifest.status -ne "PASS_R37_BLOCK8_FORMAL_CACHE" -or
    $sealedManifest.sealed_483_test_labels_read -ne $false
) {
    throw "R39 sealed Block-8 cache firewall drift"
}
$duplicates = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "train_r39_projector.py" -or
        $_.CommandLine -match "predict_r39_sealed_seed.py" -or
        $_.CommandLine -match "launch_r39_frozen_vlm.ps1"
    }
if ($duplicates) {
    throw "R39 worker/launcher still exists; refusing duplicate resume"
}

try {
    $projectors17And29 = @(
        (Start-Stage `
            -Name "projector_seed_17" `
            -Arguments @(
                "scripts\train_r39_projector.py",
                "--config", $Config,
                "--seed", "17",
                "--device", "cuda:0"
            ) `
            -Device "cuda:0" `
            -Expected (Join-Path $OutputRoot "projectors\seed_17\result.json")),
        (Start-Stage `
            -Name "projector_seed_29" `
            -Arguments @(
                "scripts\train_r39_projector.py",
                "--config", $Config,
                "--seed", "29",
                "--device", "cuda:1"
            ) `
            -Device "cuda:1" `
            -Expected (Join-Path $OutputRoot "projectors\seed_29\result.json"))
    )
    Wait-Group -Jobs $projectors17And29

    $projector43 = Start-Stage `
        -Name "projector_seed_43" `
        -Arguments @(
            "scripts\train_r39_projector.py",
            "--config", $Config,
            "--seed", "43",
            "--device", "cuda:0"
        ) `
        -Device "cuda:0" `
        -Expected (Join-Path $OutputRoot "projectors\seed_43\result.json")
    Wait-Group -Jobs @($projector43)

    $predictions17And29 = @(
        (Start-Stage `
            -Name "predict_seed_17" `
            -Arguments @(
                "scripts\predict_r39_sealed_seed.py",
                "--config", $Config,
                "--seed", "17",
                "--device", "cuda:0"
            ) `
            -Device "cuda:0" `
            -Expected (Join-Path $OutputRoot "predictions\seed_17\result.json")),
        (Start-Stage `
            -Name "predict_seed_29" `
            -Arguments @(
                "scripts\predict_r39_sealed_seed.py",
                "--config", $Config,
                "--seed", "29",
                "--device", "cuda:1"
            ) `
            -Device "cuda:1" `
            -Expected (Join-Path $OutputRoot "predictions\seed_29\result.json"))
    )
    Wait-Group -Jobs $predictions17And29

    $prediction43 = Start-Stage `
        -Name "predict_seed_43" `
        -Arguments @(
            "scripts\predict_r39_sealed_seed.py",
            "--config", $Config,
            "--seed", "43",
            "--device", "cuda:0"
        ) `
        -Device "cuda:0" `
        -Expected (Join-Path $OutputRoot "predictions\seed_43\result.json")
    Wait-Group -Jobs @($prediction43)

    Write-Status `
        -Status "PASS_R39_PRE_REVEAL_FREEZE" `
        -Stage "pre_reveal_complete" `
        -Extra @{
            all_three_projectors_frozen = $true
            all_three_prediction_sets_frozen = $true
        }
    Invoke-SerialStage `
        -Name "reveal" `
        -Arguments @(
            "scripts\reveal_r39_sealed_labels.py",
            "--config", $Config
        ) `
        -Expected (Join-Path $RevealRoot "reveal_receipt.json")
    $SealedLabelsRead = $true

    $aggregate = Start-Stage `
        -Name "aggregate" `
        -Arguments @(
            "scripts\aggregate_r39_sealed.py",
            "--config", $Config
        ) `
        -Device "cpu" `
        -Expected (Join-Path $RevealRoot "qualification.json")
    Write-Status -Status "RUNNING_R39" -Stage "aggregate" -Extra @{
        jobs = @(
            @{
                name = "aggregate"
                pid = $aggregate.Process.Id
                device = "cpu"
            }
        )
    }
    $aggregate.Process.WaitForExit()
    $aggregate.Process.Refresh()
    $aggregateExit = [int]$aggregate.Process.ExitCode
    if ($aggregateExit -notin @(0, 2)) {
        throw "aggregate failed with exit code $aggregateExit"
    }
    if (-not (
        Test-Path -LiteralPath $aggregate.Expected -PathType Leaf
    )) {
        throw "aggregate ended without a qualification artifact"
    }
    $qualification = Get-Content `
        -LiteralPath (Join-Path $RevealRoot "qualification.json") `
        -Raw | ConvertFrom-Json
    Write-Status -Status $qualification.status -Stage "complete" -Extra @{
        scientific_go = [bool]$qualification.scientific_go
        aggregate_exit_code = $aggregateExit
    }
    if ([bool]$qualification.scientific_go) { exit 0 }
    exit 2
}
catch {
    Write-Status -Status "STOP_R39_ENGINEERING" -Stage "failed" -Extra @{
        error = $_.Exception.Message
    }
    throw
}
