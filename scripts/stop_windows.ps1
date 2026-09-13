# Stop and remove the FinAlly container (Windows).
#
# Does NOT remove the `finally-data` volume -- the portfolio and chat history
# persist across stop/start cycles. Idempotent.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

docker compose down

Write-Host "FinAlly stopped. Data volume 'finally-data' preserved -- run scripts/start_windows.ps1 to resume."
