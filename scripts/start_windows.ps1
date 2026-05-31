param([switch]$Build)
$ErrorActionPreference = 'Stop'

# start_windows.ps1 - Launch the FinAlly Docker container (Windows / PowerShell).
#
# PowerShell port of scripts/start_mac.sh. Builds the `finally` image if it is
# missing (or if -Build is passed), starts a detached container with the
# persistent named volume, the env-file, and the port mapping, waits for the
# container HEALTHCHECK to report healthy, then prints the access URL.
#
# Idempotent: running it twice in a row detects an already-running container and
# prints the URL without rebuilding or duplicating containers.

# --- Resolve repo root so the script works from any cwd -----------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir '..')
Set-Location $RepoRoot

# --- Constants (must match scripts/start_mac.sh + planning/PLAN.md sec 11) -----
$Image = 'finally'
$Container = 'finally-app'
$Volume = 'finally-data'
$Port = 8000
$Url = "http://localhost:$Port"

# --- Preflight: Docker daemon must be running ---------------------------------
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Docker is not running. Start Docker Desktop and retry.'
    exit 1
}

# --- Preflight: .env presence (warn-only, never fatal) ------------------------
$EnvFile = Join-Path $RepoRoot '.env'
$EnvPresent = Test-Path $EnvFile
if (-not $EnvPresent) {
    Write-Warning '.env not found at repo root. Chat will fail without OPENROUTER_API_KEY. Copy .env.example to .env and add keys.'
}

# --- Image build logic --------------------------------------------------------
docker image inspect $Image 2>$null | Out-Null
$ImageExists = ($LASTEXITCODE -eq 0)
if ($Build -or -not $ImageExists) {
    docker build -t finally $RepoRoot
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'docker build failed'
        exit 1
    }
}
else {
    Write-Host "Using existing image $Image (pass -Build to rebuild)."
}

# --- Idempotency: inspect any existing container ------------------------------
$status = (docker inspect --format='{{.State.Status}}' $Container 2>$null)
$AlreadyRunning = $false
if ($LASTEXITCODE -eq 0) {
    if ($status -eq 'running') {
        if ($Build) {
            # A forced rebuild must take runtime effect: replace the running
            # container so it picks up the freshly built image (else -Build no-ops).
            docker rm -f $Container | Out-Null
        }
        else {
            $AlreadyRunning = $true
        }
    }
    else {
        # exited / created / paused / anything non-running: remove and re-run
        docker rm -f $Container | Out-Null
    }
}

# --- Start container (unless one is already running) --------------------------
if (-not $AlreadyRunning) {
    if ($EnvPresent) {
        & docker run -d --name $Container -v "${Volume}:/app/db" -p "${Port}:8000" --env-file $EnvFile $Image | Out-Null
    }
    else {
        & docker run -d --name $Container -v "${Volume}:/app/db" -p "${Port}:8000" $Image | Out-Null
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'docker run failed'
        exit 1
    }
}

# --- Wait for healthy (max 60 iterations, poll every 1s) ----------------------
# 60s covers Docker's own HEALTHCHECK budget (start-period 20s + 5 retries x
# 10s interval) so a slow first boot is not misreported as a script timeout.
$Healthy = $false
for ($i = 0; $i -lt 60; $i++) {
    $health = (docker inspect --format='{{.State.Health.Status}}' $Container 2>$null)
    if ($health -eq 'healthy') {
        $Healthy = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $Healthy) {
    Write-Error "container did not become healthy within 60s. Check logs: docker logs $Container"
    exit 1
}

# --- Success -----------------------------------------------------------------
Write-Host 'FinAlly is running.'
Write-Host "Open: $Url"
Write-Host 'Stop: .\scripts\stop_windows.ps1'
exit 0
