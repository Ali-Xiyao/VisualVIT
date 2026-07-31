param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("lane0", "lane1")]
    [string]$Lane
)

$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run_prta_gen_r50_method.py"

$jobs = if ($Lane -eq "lane0") {
    @(
        @("tila_ce", 17, "cuda:0"),
        @("tila_ce", 29, "cuda:0"),
        @("tila_ce", 43, "cuda:0"),
        @("tac_temporal_fusion_adapted", 17, "cuda:0"),
        @("tac_temporal_fusion_adapted", 43, "cuda:0")
    )
} else {
    @(
        @("tila_bice_tcl", 17, "cuda:1"),
        @("tila_bice_tcl", 29, "cuda:1"),
        @("tila_bice_tcl", 43, "cuda:1"),
        @("siamese_signed_abs", 17, "cuda:1"),
        @("siamese_signed_abs", 29, "cuda:1"),
        @("siamese_signed_abs", 43, "cuda:1"),
        @("tac_temporal_fusion_adapted", 29, "cuda:1")
    )
}

Push-Location $workspace
try {
    foreach ($job in $jobs) {
        $method = [string]$job[0]
        $seed = [int]$job[1]
        $device = [string]$job[2]
        Write-Output "START method=$method seed=$seed device=$device"
        & python $runner --method $method --seed $seed --device $device
        if ($LASTEXITCODE -ne 0) {
            throw "R50 method failed: method=$method seed=$seed exit=$LASTEXITCODE"
        }
        Write-Output "DONE method=$method seed=$seed device=$device"
    }
} finally {
    Pop-Location
}
