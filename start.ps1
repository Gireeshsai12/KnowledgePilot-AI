$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    docker compose up --build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
