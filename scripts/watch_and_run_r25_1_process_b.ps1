param(
    [int]$PollSeconds = 30,
    [int]$IdleMemoryMiB = 1024,
    [int]$RequiredIdleSamples = 2
)

$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $PSScriptRoot
$runtimeRoot = "F:\VisualVIT_runtime\050_routeC\r25_1_matching_qualification"
$processA = Join-Path $runtimeRoot "process_a"
$processB = Join-Path $runtimeRoot "process_b"
$logRoot = Join-Path $runtimeRoot "watcher_logs"
$watcherLog = Join-Path $logRoot "watcher.log"
$stdoutLog = Join-Path $logRoot "process_b.stdout.log"
$stderrLog = Join-Path $logRoot "process_b.stderr.log"
$verifierStdout = Join-Path $logRoot "verifier.stdout.log"
$verifierStderr = Join-Path $logRoot "verifier.stderr.log"
$certificate = Join-Path $runtimeRoot "reproduction_certificate.json"
$runner = Join-Path $workspace "scripts\run_chest_imagenome_mimic_matcher_qualification.py"
$verifier = Join-Path $workspace "scripts\verify_chest_imagenome_mimic_matcher_reproduction.py"
$protocol = Join-Path $workspace "docs\superpowers\specs\2026-07-26-r25-1-matching-qualification-v1.md"
$pythonExe = (Get-Command python -ErrorAction Stop).Source

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

function Write-WatcherLog {
    param([string]$Message)
    $timestamp = (Get-Date).ToUniversalTime().ToString("o")
    Add-Content -LiteralPath $watcherLog -Encoding UTF8 -Value "$timestamp $Message"
}

Write-WatcherLog "WATCHER_STARTED pid=$PID python=$pythonExe"
$idleSamples = 0

while ($idleSamples -lt $RequiredIdleSamples) {
    try {
        $gpu1Python = @(
            Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
                Where-Object {
                    $_.CommandLine -match "--device\s+cuda:1" -and
                    $_.CommandLine -notmatch "run_chest_imagenome_mimic_matcher_qualification.py"
                }
        )
        $gpuLine = @(
            nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
        ) | Where-Object { $_ -match "^1," } | Select-Object -First 1
        if ($null -eq $gpuLine) {
            throw "GPU1 status line is unavailable"
        }
        $match = [regex]::Match($gpuLine, "^1,\s*(\d+)\s+MiB")
        if (-not $match.Success) {
            throw "GPU1 memory could not be parsed: $gpuLine"
        }
        $usedMiB = [int]$match.Groups[1].Value
        if ($gpu1Python.Count -eq 0 -and $usedMiB -le $IdleMemoryMiB) {
            $idleSamples += 1
            Write-WatcherLog "GPU1_IDLE sample=$idleSamples/$RequiredIdleSamples used_mib=$usedMiB"
        }
        else {
            $idleSamples = 0
            $pids = ($gpu1Python | ForEach-Object { $_.ProcessId }) -join ","
            Write-WatcherLog "GPU1_BUSY used_mib=$usedMiB external_python_pids=$pids"
        }
    }
    catch {
        $idleSamples = 0
        Write-WatcherLog "GPU1_CHECK_ERROR type=$($_.Exception.GetType().Name) message=$($_.Exception.Message)"
    }
    if ($idleSamples -lt $RequiredIdleSamples) {
        Start-Sleep -Seconds $PollSeconds
    }
}

if (Test-Path -LiteralPath $processB) {
    throw "Process B output root already exists: $processB"
}
if (Test-Path -LiteralPath $certificate) {
    throw "Reproduction certificate already exists: $certificate"
}

$summaryAPath = Join-Path $processA "summary.json"
$summaryA = Get-Content -LiteralPath $summaryAPath -Raw | ConvertFrom-Json
if ($summaryA.status -ne "AWAITING_FRESH_PROCESS_REPRODUCTION") {
    throw "Process A is not compute-green: $($summaryA.status)"
}
$runnerHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $runner).Hash.ToLowerInvariant()
if ($runnerHash -ne $summaryA.source.runner_sha256) {
    throw "Runner hash drift before process B"
}
$protocolHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $protocol).Hash.ToLowerInvariant()
if ($protocolHash -ne $summaryA.protocol.sha256) {
    throw "Protocol hash drift before process B"
}

Write-WatcherLog "PROCESS_B_START runner_sha=$runnerHash protocol_sha=$protocolHash"
$processBArgs = @(
    $runner,
    "--output-root", $processB,
    "--process-id", "b",
    "--device", "cuda:1",
    "--batch-size", "64",
    "--bootstrap-replicates", "10000"
)
$processBRun = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList $processBArgs `
    -WorkingDirectory $workspace `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -Wait `
    -PassThru
Write-WatcherLog "PROCESS_B_EXIT code=$($processBRun.ExitCode)"
if ($processBRun.ExitCode -ne 0) {
    throw "Process B failed with exit code $($processBRun.ExitCode)"
}

$summaryBPath = Join-Path $processB "summary.json"
$verifierArgs = @(
    $verifier,
    "--process-a", $summaryAPath,
    "--process-b", $summaryBPath,
    "--output", $certificate
)
Write-WatcherLog "Q6_VERIFIER_START"
$verifierRun = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList $verifierArgs `
    -WorkingDirectory $workspace `
    -RedirectStandardOutput $verifierStdout `
    -RedirectStandardError $verifierStderr `
    -WindowStyle Hidden `
    -Wait `
    -PassThru
Write-WatcherLog "Q6_VERIFIER_EXIT code=$($verifierRun.ExitCode)"
if ($verifierRun.ExitCode -ne 0) {
    throw "Q6 verifier failed with exit code $($verifierRun.ExitCode)"
}

$certificatePayload = Get-Content -LiteralPath $certificate -Raw | ConvertFrom-Json
if (
    $certificatePayload.status -ne "PASS_Q6_FRESH_PROCESS_REPRODUCTION" -or
    $certificatePayload.qualified -ne $true
) {
    throw "Q6 certificate is not terminal green"
}
Write-WatcherLog "WATCHER_COMPLETE certificate=$certificate"
