# Save everything and send it to GitHub in one go.
#   .\push.ps1                      commits with a dated message
#   .\push.ps1 "fixed the overlay"  commits with your message
# The add-on source in addon/dips-Score goes up with everything else.
param([string]$Message = "")

Set-Location $PSScriptRoot

# addon\dips-Score here is the add-on's only copy. Link the game to it once (folder junction):
#   New-Item -ItemType Junction -Path "<WoW>\Interface\AddOns\dips-Score" -Target "$PSScriptRoot\addon\dips-Score"

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
