param(
  [Parameter(Mandatory=$true)][ValidateSet('prepare','image','video','summary','report','verify')][string]$Command,
  [string]$RunId = 'visual-20261023',
  [Parameter(Mandatory=$true)][string]$EnvironmentPrefix,
  [string]$Config = 'vision\configs\default.yaml'
)
$ErrorActionPreference = 'Stop'
$workspacePath = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $workspacePath
try {
  $env:PYTHONNOUSERSITE = '1'
  conda run --no-capture-output -p $EnvironmentPrefix python -s -m vision $Command --config $Config --run-id $RunId
  if ($LASTEXITCODE -ne 0) { throw "Experiment command failed with exit $LASTEXITCODE" }
} finally { Pop-Location }
