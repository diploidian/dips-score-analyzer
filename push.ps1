# Save everything and send it to GitHub in one go.
#   .\push.ps1                      commits with a dated message
#   .\push.ps1 "fixed the overlay"  commits with your message
# It first copies the add-on from your WoW folder into addon/dips-Score, so add-on changes go up too.
param([string]$Message = "")

Set-Location $PSScriptRoot

$AddOn = "D:\Program Files (x86)\World of Warcraft\_forever_\Interface\AddOns\dips-Score"
if (Test-Path $AddOn) {
    robocopy $AddOn "addon\dips-Score" /MIR /XD .git /NFL /NDL /NJH /NJS /NP | Out-Null
} else {
    Write-Host "Add-on folder not found, skipping it: $AddOn" -ForegroundColor DarkGray
}

if (-not (git remote)) {
    Write-Host "No GitHub repo linked yet. Run this once (with your repo's address):" -ForegroundColor Yellow
    Write-Host "  git remote add origin https://github.com/<you>/dips-score-analyzer.git"
    exit 1
}

git add -A
if (git status --porcelain) {
    if (-not $Message) { $Message = "Update " + (Get-Date -Format "yyyy-MM-dd HH:mm") }
    git commit -m $Message
} else {
    Write-Host "Nothing new to commit." -ForegroundColor DarkGray
}

git push -u origin HEAD
if ($LASTEXITCODE -eq 0) { Write-Host "Pushed." -ForegroundColor Green }
