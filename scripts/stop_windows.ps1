# Stop and remove the FinAlly container (Windows PowerShell). Idempotent.
# The finally-data volume is preserved so the database survives restarts.
$ErrorActionPreference = "Stop"

$ContainerName = "finally"

$existing = docker ps -a --format '{{.Names}}'
if ($existing -split "`n" | Where-Object { $_ -eq $ContainerName }) {
    Write-Host "Stopping FinAlly..."
    docker stop $ContainerName *> $null
    docker rm $ContainerName | Out-Null
    Write-Host "Stopped. (The finally-data volume was kept.)"
} else {
    Write-Host "FinAlly is not running."
}
