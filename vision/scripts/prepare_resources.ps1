param(
    [Parameter(Mandatory=$true)][string]$AssetRoot,
    [Parameter(Mandatory=$true)][string]$EnvironmentPath,
    [string]$CondaExecutable = 'conda'
)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Push-Location -LiteralPath $workspace
try {
    & $CondaExecutable run -p $EnvironmentPath python -s -m vision.common.resources --asset-root $AssetRoot
    if ($LASTEXITCODE -ne 0) { throw "公开资源准备失败，退出码 $LASTEXITCODE；保留的部分下载可供重试。" }
} finally { Pop-Location }
