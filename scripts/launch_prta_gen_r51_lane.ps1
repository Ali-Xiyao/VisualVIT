param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("lane0", "lane1")]
    [string]$Lane
)

$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run_prta_gen_r51_matched_interface.py"
$config = Join-Path $workspace "configs\prta_gen\prta_gen_r51_matched_interface_v1.json"

$jobs = if ($Lane -eq "lane0") {
    @(
        @("prta_exact64", 17, "cuda:0"),
        @("tila_exact64", 17, "cuda:0"),
        @("b2_exact64", 17, "cuda:0"),
        @("prta_exact64", 43, "cuda:0"),
        @("tila_exact64", 43, "cuda:0")
    )
} else {
    @(
        @("prta_exact64", 29, "cuda:1"),
        @("tila_exact64", 29, "cuda:1"),
        @("b2_exact64", 29, "cuda:1"),
        @("b2_exact64", 43, "cuda:1")
    )
}

Push-Location $workspace
try {
    foreach ($job in $jobs) {
        $arm = [string]$job[0]
        $seed = [int]$job[1]
        $device = [string]$job[2]
        Write-Output "START arm=$arm seed=$seed device=$device"
        & python $runner --config $config --arm $arm --seed $seed --device $device
        if ($LASTEXITCODE -ne 0) {
            throw "R51 arm failed: arm=$arm seed=$seed exit=$LASTEXITCODE"
        }
        Write-Output "DONE arm=$arm seed=$seed device=$device"
    }
} finally {
    Pop-Location
}
