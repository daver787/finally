$ErrorActionPreference = 'Stop'

# stop_windows.ps1 - Stop and remove the FinAlly Docker container (Windows / PowerShell).
#
# PowerShell port of scripts/stop_mac.sh. Stops + removes the running container
# but NEVER touches the named volume, so all SQLite data (positions, trades,
# watchlist, chat history) persists and reloads on the next start. Idempotent:
# running it when no container exists exits 0 with an informational message
# rather than an error.

# --- Constants (must match start_windows.ps1) --------------------------------
$Container = 'finally-app'
$Volume = 'finally-data'

# --- Preflight: Docker daemon must be running --------------------------------
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Docker is not running. Start Docker Desktop and retry.'
    exit 1
}

# --- Idempotent stop ---------------------------------------------------------
# `docker rm -f` force-stops then removes in one call, avoiding the
# stop-succeeds-then-rm-against-running race ($ErrorActionPreference does not
# trap native exe exit codes, so we check $LASTEXITCODE explicitly).
docker inspect $Container 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    docker rm -f $Container | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "failed to remove $Container."
        exit 1
    }
    Write-Host "Stopped and removed container $Container."
}
else {
    Write-Host "No container named $Container is running."
}

# --- Volume preservation guard -----------------------------------------------
# The named volume is intentionally left untouched. This script must NEVER
# delete it - doing so would destroy all persistent user data (SCPT-03).
Write-Host "Volume $Volume preserved. Data will reload on next start."
exit 0
