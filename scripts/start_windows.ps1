# Start the FinAlly container (Windows PowerShell). Idempotent.
$ErrorActionPreference = "Stop"

$ImageName     = "finally"
$ContainerName = "finally"
$Url           = "http://localhost:8000"
$ProjectRoot   = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# Already running? Just report and exit.
$running = docker ps --format '{{.Names}}'
if ($running -split "`n" | Where-Object { $_ -eq $ContainerName }) {
    Write-Host "FinAlly is already running at $Url"
    exit 0
}

# Remove a stopped container of the same name so the run below succeeds.
$existing = docker ps -a --format '{{.Names}}'
if ($existing -split "`n" | Where-Object { $_ -eq $ContainerName }) {
    Write-Host "Removing stopped container..."
    docker rm $ContainerName | Out-Null
}

# Ensure a .env file exists (--env-file requires it).
$EnvFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "No .env found. Copying .env.example -> .env (edit it to add your API keys)."
    Copy-Item (Join-Path $ProjectRoot ".env.example") $EnvFile
}

# Build the image if requested with --build or if it does not exist yet.
$imageExists = $true
docker image inspect $ImageName *> $null
if ($LASTEXITCODE -ne 0) { $imageExists = $false }

if ($args[0] -eq "--build" -or -not $imageExists) {
    Write-Host "Building FinAlly image..."
    docker build -t $ImageName $ProjectRoot
}

Write-Host "Starting FinAlly..."
docker run -d `
  --name $ContainerName `
  --restart unless-stopped `
  -v finally-data:/app/db `
  -p 8000:8000 `
  --env-file $EnvFile `
  $ImageName | Out-Null

Write-Host "FinAlly is running at $Url"
Start-Sleep -Seconds 2
Start-Process $Url
