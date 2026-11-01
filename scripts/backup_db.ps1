[CmdletBinding()]
param(
    [ValidateSet('backup', 'restore', 'verify')]
    [string]$Action = 'backup',
    [string]$BackupFile,
    [string]$BackupDirectory = (Join-Path (Get-Location) 'backups'),
    [string]$TargetDatabaseUrl,
    [switch]$ConfirmRestore
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-DatabaseUrl {
    param([string]$Override)
    $value = ($Override ?? $env:DATABASE_URL).Trim()
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw 'Set DATABASE_URL or pass -TargetDatabaseUrl. Do not put credentials in this script.'
    }
    if ($value -notmatch '^postgresql(?:\+[^:]+)?://') {
        throw 'DATABASE_URL must be a PostgreSQL connection URL.'
    }
    return $value
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name was not found on PATH. Install PostgreSQL client tools first."
    }
}

function New-SafeBackupPath {
    param([string]$Directory)
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    return Join-Path (Resolve-Path $Directory) "neuroops-$stamp.sql"
}

function Invoke-Backup {
    Require-Command 'pg_dump'
    $databaseUrl = Get-DatabaseUrl
    $path = if ($BackupFile) { [IO.Path]::GetFullPath($BackupFile) } else { New-SafeBackupPath $BackupDirectory }
    $parent = Split-Path -Parent $path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    if (Test-Path $path) { throw "Refusing to overwrite existing backup: $path" }

    & pg_dump --dbname=$databaseUrl --format=plain --no-owner --no-privileges --file=$path
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE." }
    if ((Get-Item $path).Length -le 0) { throw 'pg_dump produced an empty backup.' }
    Write-Output "Backup created: $path"
}

function Invoke-Verify {
    Require-Command 'psql'
    $databaseUrl = Get-DatabaseUrl
    & psql --dbname=$databaseUrl --set=ON_ERROR_STOP=1 --command='SELECT current_database(), current_user;'
    if ($LASTEXITCODE -ne 0) { throw "psql connectivity check failed with exit code $LASTEXITCODE." }
    Write-Output 'Database connectivity check passed.'
}

function Invoke-Restore {
    Require-Command 'psql'
    if (-not $BackupFile) { throw 'Restore requires -BackupFile.' }
    $path = [IO.Path]::GetFullPath($BackupFile)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Backup file not found: $path" }
    if (-not $ConfirmRestore) {
        throw 'Restore is destructive. Re-run with -ConfirmRestore and an explicit target database URL.'
    }
    if (-not $TargetDatabaseUrl) {
        throw 'Restore requires -TargetDatabaseUrl so the destination is explicit.'
    }

    $databaseUrl = Get-DatabaseUrl $TargetDatabaseUrl
    Write-Warning "Restoring $path into the explicitly supplied target database. Existing rows may be changed."
    & psql --dbname=$databaseUrl --set=ON_ERROR_STOP=1 --file=$path
    if ($LASTEXITCODE -ne 0) { throw "psql restore failed with exit code $LASTEXITCODE." }
    Write-Output 'Restore completed.'
}

switch ($Action) {
    'backup'  { Invoke-Backup }
    'verify'  { Invoke-Verify }
    'restore' { Invoke-Restore }
}
