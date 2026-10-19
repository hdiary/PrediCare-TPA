$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & docker compose --profile backup run --rm --build -T db-backup backup.sh
    if ($LASTEXITCODE -ne 0) {
        throw "Encrypted backup failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
