param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$BackupFile,
    [switch]$VerifyOnly,
    [string]$TargetDb
)

$ErrorActionPreference = "Stop"
$backupName = Split-Path -Leaf $BackupFile
if ($backupName -notmatch '^predicare_.+\.dump\.gpg$') {
    throw "Provide the name of a predicare_*.dump.gpg file in .\backups."
}
if ($VerifyOnly -and $TargetDb) {
    throw "-VerifyOnly and -TargetDb cannot be used together."
}

$restoreOptions = @()
if ($VerifyOnly) {
    $restoreOptions += "--verify-only"
}
elseif ($TargetDb) {
    $restoreOptions += @("--target-db", $TargetDb)
}
else {
    throw "Specify -VerifyOnly or -TargetDb."
}

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & docker compose --profile backup run --rm --build -T db-backup `
        restore.sh "/backups/$backupName" @restoreOptions
    if ($LASTEXITCODE -ne 0) {
        throw "Restore failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
