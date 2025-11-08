# Drive Cleanup Toolkit - Activation Script
# Run this with: . .\activate.ps1

$venvPath = Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"

if (Test-Path $venvPath) {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & $venvPath
    Write-Host "✓ Virtual environment activated!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Available commands:" -ForegroundColor Cyan
    Write-Host "  python gui_toolkit.py          - Launch GUI interface"
    Write-Host "  python scan_storage.py --help  - Scan and index files"
    Write-Host "  python drive_organizer.py --help - Organize/dedupe files"
    Write-Host ""
    Write-Host "Remember to use --dry-run flag first!" -ForegroundColor Yellow
} else {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Run: python -m venv venv" -ForegroundColor Yellow
    Write-Host "Then: pip install -r requirements.txt" -ForegroundColor Yellow
}
