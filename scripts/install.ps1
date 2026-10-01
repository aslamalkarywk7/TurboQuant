#Requires -Version 5.1
# تثبيت TurboQuant بنقرة واحدة (Windows PowerShell)
# Usage: powershell -ExecutionPolicy Bypass -File scripts/install.ps1
$ErrorActionPreference = "Stop"
Write-Host "Installing TurboQuant..." -ForegroundColor Cyan
python -m pip install --upgrade pip
pip install -e ".[max]"
python -m turboquant detect --help | Out-Null
Write-Host "Done! Try: python -m turboquant lossless <file> -o out.tqz --mode max" -ForegroundColor Green
