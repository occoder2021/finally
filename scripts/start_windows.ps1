# Build and start the FinAlly container (Windows).
#
# Idempotent -- safe to run multiple times. All port/volume/env configuration
# lives in docker-compose.yml; this script only wraps `docker compose`.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example."
        Write-Host "Edit .env and add your OPENROUTER_API_KEY (optional but needed for AI chat), then re-run this script."
        exit 1
    } else {
        Write-Error "Missing .env and .env.example -- cannot start. See planning/PLAN.md section 5 for required variables."
        exit 1
    }
}

docker compose up -d --build

Write-Host "FinAlly is starting -- waiting for it to become healthy..."

$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        # Not ready yet -- keep polling.
    }
    Start-Sleep -Seconds 1
}

if ($ready) {
    Write-Host "FinAlly is ready: http://localhost:8000"
    Start-Process "http://localhost:8000"
} else {
    Write-Warning "FinAlly did not report healthy within 30s -- check 'docker compose logs' for details."
    exit 1
}
