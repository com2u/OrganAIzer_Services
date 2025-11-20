# Git Push Script
# Usage: .\git_push.ps1 "Your commit message here"

param(
    [Parameter(Mandatory=$true)]
    [string]$CommitMessage
)

Write-Host "=== Git Push Script ===" -ForegroundColor Cyan
Write-Host ""

# Add all files
Write-Host "Adding all files to git..." -ForegroundColor Yellow
git add .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to add files to git" -ForegroundColor Red
    exit 1
}

Write-Host "Files added successfully!" -ForegroundColor Green
Write-Host ""

# Commit with message
Write-Host "Committing changes with message: '$CommitMessage'" -ForegroundColor Yellow
git commit -m $CommitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to commit changes" -ForegroundColor Red
    Write-Host "Note: This might be because there are no changes to commit" -ForegroundColor Yellow
    exit 1
}

Write-Host "Changes committed successfully!" -ForegroundColor Green
Write-Host ""

# Push to remote
Write-Host "Pushing changes to remote repository..." -ForegroundColor Yellow
git push

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to push changes to remote" -ForegroundColor Red
    exit 1
}

Write-Host "Changes pushed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "=== All operations completed successfully! ===" -ForegroundColor Cyan
