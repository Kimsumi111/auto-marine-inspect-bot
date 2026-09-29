$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    dotnet run --project (Join-Path $PSScriptRoot 'MarineMonitor/MarineMonitor.csproj')
    if ($LASTEXITCODE -ne 0) { throw "Dashboard exited with code $LASTEXITCODE" }
}
finally { Pop-Location }
