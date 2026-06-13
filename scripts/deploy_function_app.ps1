<#
.SYNOPSIS
  Canonical deploy for the PathForward MCP Azure Function App (mint / gate / fabric / route).

.DESCRIPTION
  functions/mint_mcp/function_app.py imports the repo-root `pathforward` package, which is neither
  pip-installed nor stored under the function folder. This script assembles a clean, self-contained
  deploy package in a gitignored staging dir (function files + the pathforward package), publishes it
  with a remote build, and removes the staging dir. This is the ONE supported way to deploy the
  Function App -- no manual copying, no ad-hoc workarounds.

.PARAMETER FunctionApp
  Target Function App name. Default: pathforward-mint-mcp-34786.

.PARAMETER StageOnly
  Assemble and list the package but do NOT publish (dry run for inspection).

.PARAMETER Smoke
  After publishing, run scripts/smoke_mcp_endpoints.py against the live endpoints.

.EXAMPLE
  ./scripts/deploy_function_app.ps1 -StageOnly      # inspect the package, no live change
  ./scripts/deploy_function_app.ps1 -Smoke          # publish, then verify endpoints
#>
[CmdletBinding()]
param(
    [string]$FunctionApp = "pathforward-mint-mcp-34786",
    [switch]$StageOnly,
    [switch]$Smoke
)
$ErrorActionPreference = "Stop"
$root  = Split-Path -Parent $PSScriptRoot
$src   = Join-Path $root "functions\mint_mcp"
$pkg   = Join-Path $root "pathforward"
$stage = Join-Path $src ".deploy"

function Require-Exe([string]$name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Required executable '$name' not found on PATH."
    }
}

# 1. Preconditions
Require-Exe func
Require-Exe az
if (-not (Test-Path (Join-Path $src "function_app.py"))) { throw "function_app.py not found under $src" }
if (-not (Test-Path $pkg)) { throw "pathforward package not found at $pkg" }
$acct = az account show -o json | ConvertFrom-Json
Write-Host "func   : $((func --version) 2>&1 | Select-Object -First 1)"
Write-Host "account: $($acct.user.name) [$($acct.user.type)] sub=$($acct.id)"
Write-Host "target : $FunctionApp"

# 2. Assemble a clean, self-contained package in the gitignored staging dir
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
foreach ($f in @("function_app.py", "host.json", "requirements.txt", ".funcignore")) {
    Copy-Item (Join-Path $src $f) (Join-Path $stage $f) -Force
}
Copy-Item $pkg (Join-Path $stage "pathforward") -Recurse -Force
Get-ChildItem -Path $stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Path $stage -Recurse -File -Include *.pyc | Remove-Item -Force

# func reads FUNCTIONS_WORKER_RUNTIME locally to pick the language. .funcignore excludes
# local.settings.json from the upload, so this stays local and is never deployed.
$localSettings = '{"IsEncrypted":false,"Values":{"FUNCTIONS_WORKER_RUNTIME":"python","AzureWebJobsStorage":""}}'
Set-Content -Path (Join-Path $stage "local.settings.json") -Value $localSettings -Encoding utf8

Write-Host "`nStaged package ($stage):"
Get-ChildItem $stage -Name
Write-Host "pathforward/ subpackages:"
Get-ChildItem (Join-Path $stage "pathforward") -Directory -Name

if ($StageOnly) {
    Write-Host "`n-StageOnly: package assembled; publish skipped. Staging left in place for inspection."
    return
}

# 3. Publish (remote build) from the staged dir; always clean up
Push-Location $stage
try {
    func azure functionapp publish $FunctionApp --python --build remote
    if ($LASTEXITCODE -ne 0) { throw "func publish failed (exit $LASTEXITCODE)" }
}
finally {
    Pop-Location
    if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
}
Write-Host "`nPublished $FunctionApp (staging removed)."

# 4. Optional endpoint smoke
if ($Smoke) {
    $py = Join-Path $root ".venv\Scripts\python.exe"
    & $py (Join-Path $root "scripts\smoke_mcp_endpoints.py")
}
