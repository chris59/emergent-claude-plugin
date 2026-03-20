# Syncs plugin source to Claude's plugin cache
# Run after editing plugin files: .\tools\emergent-claude-plugin\sync-to-cache.ps1
$source = $PSScriptRoot
$cache = "$env:USERPROFILE\.claude\plugins\cache\emergent-tools\emergent-dev\1.0.0"

if (-not (Test-Path $cache)) {
    New-Item -ItemType Directory -Force -Path $cache | Out-Null
}

# Remove old cache contents (but not the directory itself)
Get-ChildItem $cache | Remove-Item -Recurse -Force

# Copy fresh from source
Get-ChildItem $source -Exclude ".git", "sync-to-cache.ps1" | Copy-Item -Destination $cache -Recurse -Force

Write-Host "Plugin synced to cache. Restart Claude to pick up changes." -ForegroundColor Green
