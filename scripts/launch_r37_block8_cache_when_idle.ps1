param(
    [string]$Workspace = "E:\Xiyaowang\050_VisualVIT",
    [string]$RuntimeRoot = "H:\VisualVIT_runtime\050_routeD\r37_prta_cxr",
    [int]$PollSeconds = 60,
    [int]$RequiredIdlePolls = 3,
    [int]$MaximumUsedMiB = 2000
)

$ErrorActionPreference = "Stop"
$pythonExecutable = (Get-Command python).Source
$cacheRoot = Join-Path $RuntimeRoot "r37_block8_token_cache"
$monitorLog = Join-Path $RuntimeRoot "r37_block8_idle_launcher.log"
$statusPath = Join-Path $RuntimeRoot "r37_block8_idle_launcher_status.json"

function Write-MonitorLog {
    param([string]$Message)
    $line = "$(Get-Date -Format o) $Message"
    Add-Content -LiteralPath $monitorLog -Value $line -Encoding UTF8
}

function Write-Status {
    param(
        [string]$Status,
        [hashtable]$Extra = @{}
    )
    $payload = @{
        schema = "visualvit.r37.block8-idle-launcher.v1"
        status = $Status
        updated_at = (Get-Date -Format o)
        workspace = $Workspace
        runtime_root = $RuntimeRoot
        cache_root = $cacheRoot
        source_hashes_recomputed = $false
        protected_outcomes_read = $false
    }
    foreach ($key in $Extra.Keys) {
        $payload[$key] = $Extra[$key]
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $statusPath -Encoding UTF8
}

New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
if (Test-Path -LiteralPath $cacheRoot) {
    Write-Status -Status "STOP_CACHE_ROOT_ALREADY_EXISTS"
    throw "Formal cache root already exists: $cacheRoot"
}
if ($PollSeconds -lt 10) {
    throw "PollSeconds must be at least 10"
}
if ($RequiredIdlePolls -lt 1) {
    throw "RequiredIdlePolls must be positive"
}

Write-MonitorLog "launcher started; waiting for both GPUs to remain below ${MaximumUsedMiB} MiB"
Write-Status -Status "WAITING_FOR_GPU_IDLE" -Extra @{
    required_idle_polls = $RequiredIdlePolls
    maximum_used_mib = $MaximumUsedMiB
}

$idlePolls = 0
while ($idlePolls -lt $RequiredIdlePolls) {
    $used = @(
        nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits |
            ForEach-Object { [int]$_.Trim() }
    )
    if ($LASTEXITCODE -ne 0 -or $used.Count -ne 2) {
        $idlePolls = 0
        Write-MonitorLog "GPU query failed or did not return exactly two devices"
    }
    elseif (($used | Where-Object { $_ -ge $MaximumUsedMiB }).Count -eq 0) {
        $idlePolls += 1
        Write-MonitorLog "idle confirmation $idlePolls/$RequiredIdlePolls; used_mib=$($used -join ',')"
    }
    else {
        $idlePolls = 0
        Write-MonitorLog "GPUs busy; used_mib=$($used -join ',')"
    }
    Write-Status -Status "WAITING_FOR_GPU_IDLE" -Extra @{
        idle_polls = $idlePolls
        required_idle_polls = $RequiredIdlePolls
        observed_used_mib = $used
        maximum_used_mib = $MaximumUsedMiB
    }
    if ($idlePolls -lt $RequiredIdlePolls) {
        Start-Sleep -Seconds $PollSeconds
    }
}

if (Test-Path -LiteralPath $cacheRoot) {
    Write-Status -Status "STOP_CACHE_ROOT_CREATED_DURING_WAIT"
    throw "Formal cache root appeared during idle wait: $cacheRoot"
}

$part0Out = Join-Path $RuntimeRoot "r37_block8_part0.stdout.log"
$part0Err = Join-Path $RuntimeRoot "r37_block8_part0.stderr.log"
$part1Out = Join-Path $RuntimeRoot "r37_block8_part1.stdout.log"
$part1Err = Join-Path $RuntimeRoot "r37_block8_part1.stderr.log"
$common = @(
    "scripts\cache_r37_block8_tokens.py",
    "--full",
    "--part-count", "2",
    "--batch-size", "128",
    "--workers", "8"
)
$part0Args = $common + @("--part-index", "0", "--device", "cuda:0")
$part1Args = $common + @("--part-index", "1", "--device", "cuda:1")

Write-MonitorLog "starting two formal cache parts"
$part0 = Start-Process -FilePath $pythonExecutable -ArgumentList $part0Args `
    -WorkingDirectory $Workspace -WindowStyle Hidden `
    -RedirectStandardOutput $part0Out -RedirectStandardError $part0Err -PassThru
$part1 = Start-Process -FilePath $pythonExecutable -ArgumentList $part1Args `
    -WorkingDirectory $Workspace -WindowStyle Hidden `
    -RedirectStandardOutput $part1Out -RedirectStandardError $part1Err -PassThru
Write-Status -Status "CACHE_PARTS_RUNNING" -Extra @{
    part0_pid = $part0.Id
    part1_pid = $part1.Id
    part0_stdout = $part0Out
    part0_stderr = $part0Err
    part1_stdout = $part1Out
    part1_stderr = $part1Err
}

$part0.WaitForExit()
$part1.WaitForExit()
$part0Exit = $part0.ExitCode
$part1Exit = $part1.ExitCode
$part0Failed = $null -ne $part0Exit -and [int]$part0Exit -ne 0
$part1Failed = $null -ne $part1Exit -and [int]$part1Exit -ne 0
$part0Display = if ($null -eq $part0Exit) { "unavailable" } else { $part0Exit }
$part1Display = if ($null -eq $part1Exit) { "unavailable" } else { $part1Exit }
Write-MonitorLog "cache parts exited; part0=$part0Display part1=$part1Display"
if ($part0Failed -or $part1Failed) {
    Write-Status -Status "STOP_R37_BLOCK8_CACHE_PART_FAILURE" -Extra @{
        part0_exit_code = $part0Exit
        part1_exit_code = $part1Exit
    }
    exit 2
}

$mergeOut = Join-Path $RuntimeRoot "r37_block8_merge.stdout.log"
$mergeErr = Join-Path $RuntimeRoot "r37_block8_merge.stderr.log"
$merge = Start-Process -FilePath $pythonExecutable -ArgumentList @(
    "scripts\merge_r37_block8_cache_parts.py",
    "--cache-root", $cacheRoot,
    "--part-count", "2"
) -WorkingDirectory $Workspace -WindowStyle Hidden `
    -RedirectStandardOutput $mergeOut -RedirectStandardError $mergeErr -PassThru
$merge.WaitForExit()
if ($merge.ExitCode -ne 0) {
    Write-Status -Status "STOP_R37_BLOCK8_CACHE_MERGE_FAILURE" -Extra @{
        merge_exit_code = $merge.ExitCode
        merge_stdout = $mergeOut
        merge_stderr = $mergeErr
    }
    exit 3
}

Write-MonitorLog "formal Block-8 cache completed and merged"
Write-Status -Status "PASS_R37_BLOCK8_FORMAL_CACHE" -Extra @{
    merged_manifest = (Join-Path $cacheRoot "cache_manifest.json")
    part0_exit_code = $part0Exit
    part1_exit_code = $part1Exit
    process_exit_codes_available = (
        $null -ne $part0Exit -and $null -ne $part1Exit
    )
}
exit 0
