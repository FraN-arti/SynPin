# SynPin Sync Script
# Copies from D:\synpin (dev) to ~/.synpin (production)
#
# Usage: .\scripts\sync.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SynPin - Sync Dev to Production" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$DEV_DIR = "D:\synpin"
$PROD_DIR = Join-Path $env:USERPROFILE ".synpin"

# Check dev directory
if (-not (Test-Path $DEV_DIR)) {
    Write-Host "ERROR: Dev directory not found: $DEV_DIR" -ForegroundColor Red
    exit 1
}

# Check if prod exists
$prodExists = Test-Path $PROD_DIR

if ($prodExists) {
    Write-Host "[1/3] Stopping SynPin if running..." -ForegroundColor Yellow
    # Try to stop running server
    $process = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*synpin*"
    }
    if ($process) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Write-Host "  OK: Stopped running server" -ForegroundColor Green
    } else {
        Write-Host "  OK: No running server found" -ForegroundColor Green
    }
} else {
    Write-Host "[1/3] Creating production directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $PROD_DIR -Force | Out-Null
    Write-Host "  OK: Created $PROD_DIR" -ForegroundColor Green
}

Write-Host ""
Write-Host "[2/3] Syncing files..." -ForegroundColor Yellow

# Helper function
function Sync-Directory($src, $dst, $exclude) {
    if (-not (Test-Path $dst)) {
        New-Item -ItemType Directory -Path $dst -Force | Out-Null
    }
    
    Get-ChildItem -Path $src -Directory | Where-Object { $_.Name -notin $exclude } | ForEach-Object {
        $srcPath = $_.FullName
        $dstPath = Join-Path $dst $_.Name
        Sync-Directory $srcPath $dstPath $exclude
    }
    
    Get-ChildItem -Path $src -File | ForEach-Object {
        $srcPath = $_.FullName
        $dstPath = Join-Path $dst $_.Name
        Copy-Item $srcPath $dstPath -Force
    }
}

# Sync core (excluding .venv)
Write-Host "  Syncing core..." -ForegroundColor Gray
$devCore = Join-Path $DEV_DIR "core"
$prodCore = Join-Path $PROD_DIR "core"
if (Test-Path $devCore) {
    if (-not (Test-Path $prodCore)) { New-Item -ItemType Directory -Path $prodCore -Force | Out-Null }
    Get-ChildItem $devCore -Directory | Where-Object { $_.Name -ne ".venv" } | ForEach-Object {
        $src = $_.FullName
        $dst = Join-Path $prodCore $_.Name
        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
        Copy-Item $src $dst -Recurse -Force
    }
    Get-ChildItem $devCore -File | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $prodCore $_.Name) -Force
    }
    Write-Host "  OK: Core synced" -ForegroundColor Green
}

# Sync web (excluding node_modules, dist)
Write-Host "  Syncing web..." -ForegroundColor Gray
$devWeb = Join-Path $DEV_DIR "web"
$prodWeb = Join-Path $PROD_DIR "web"
if (Test-Path $devWeb) {
    if (-not (Test-Path $prodWeb)) { New-Item -ItemType Directory -Path $prodWeb -Force | Out-Null }
    Get-ChildItem $devWeb -Directory | Where-Object { $_.Name -notin @("node_modules", "dist") } | ForEach-Object {
        $src = $_.FullName
        $dst = Join-Path $prodWeb $_.Name
        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
        Copy-Item $src $dst -Recurse -Force
    }
    Get-ChildItem $devWeb -File | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $prodWeb $_.Name) -Force
    }
    Write-Host "  OK: Web synced" -ForegroundColor Green
}

# Sync wiki
Write-Host "  Syncing wiki..." -ForegroundColor Gray
$devWiki = Join-Path $DEV_DIR "wiki"
$prodWiki = Join-Path $PROD_DIR "wiki"
if (Test-Path $devWiki) {
    if (Test-Path $prodWiki) { Remove-Item $prodWiki -Recurse -Force }
    Copy-Item $devWiki $prodWiki -Recurse -Force
    Write-Host "  OK: Wiki synced" -ForegroundColor Green
}

# Sync other files
Write-Host "  Syncing other files..." -ForegroundColor Gray
Get-ChildItem $DEV_DIR -File | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $PROD_DIR $_.Name) -Force
}

Write-Host ""
Write-Host "[3/3] Building Web UI..." -ForegroundColor Yellow

$prodWebDir = Join-Path $PROD_DIR "web"
Push-Location $prodWebDir

# Install dependencies if node_modules doesn't exist
if (-not (Test-Path "node_modules")) {
    Write-Host "  Installing dependencies..." -ForegroundColor Gray
    npm ci --silent 2>&1 | Out-Null
}

# Build
Write-Host "  Building..." -ForegroundColor Gray
$buildResult = npm run build 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Build failed!" -ForegroundColor Red
    Write-Host $buildResult -ForegroundColor Red
    Pop-Location
    exit 1
}

Pop-Location
Write-Host "  OK: Web built" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Sync complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Start with: synpin start" -ForegroundColor Yellow
Write-Host ""
