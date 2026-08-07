# Builds yt-dlp-gui for Windows and wraps it in an installer .exe.
#
# Requires: Python 3 with tkinter, PyInstaller, and Inno Setup 6 (ISCC.exe).
#   py -m pip install pyinstaller
#   winget install JRSoftware.InnoSetup
#
# Usage: powershell -ExecutionPolicy Bypass -File packaging\windows\release.ps1
param(
  [string]$Version = "1.0.0",
  [switch]$SkipVendor,
  [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$DistDir = Join-Path $ProjectRoot "dist\windows"
$AppDir = Join-Path $DistDir "yt-dlp-gui"
$VendorBin = Join-Path $ProjectRoot "vendor\win\bin"

if (-not $SkipVendor -and -not (Test-Path $VendorBin)) {
  Write-Host "== Fetching vendored tools =="
  & (Join-Path $PSScriptRoot "fetch_vendor.ps1")
}

Write-Host "== Building with PyInstaller =="
# Fresh Windows installs expose the launcher as `py` rather than `python`.
$Python = if (Get-Command python -ErrorAction SilentlyContinue) { "python" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" }
else { throw "No Python found on PATH. Install Python 3 from python.org (tick 'Add to PATH')." }

& $Python -m PyInstaller (Join-Path $PSScriptRoot "yt-dlp-gui.spec") `
  --noconfirm `
  --distpath $DistDir `
  --workpath (Join-Path $ProjectRoot "build\windows")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# The bundled tools must land next to the app, or downloads fall back to PATH.
$BundledTools = Join-Path $AppDir "_internal\tools\bin"
if (-not (Test-Path (Join-Path $BundledTools "yt-dlp.exe"))) {
  throw "Bundled yt-dlp.exe missing from $BundledTools"
}
Write-Host "Bundled tools OK: $((Get-ChildItem $BundledTools).Name -join ', ')"

if ($SkipInstaller) {
  Write-Host "`nBuilt $AppDir (installer skipped)."
  exit 0
}

Write-Host "== Compiling installer =="
$Iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($Iscc) {
  $IsccPath = $Iscc.Source
}
else {
  $IsccPath = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $IsccPath) {
  throw "ISCC.exe not found. Install Inno Setup 6 (winget install JRSoftware.InnoSetup) or pass -SkipInstaller."
}

& $IsccPath "/DAppVersion=$Version" (Join-Path $PSScriptRoot "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

Write-Host ""
Get-ChildItem (Join-Path $DistDir "*-setup.exe") |
  Select-Object FullName, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 1) } } | Format-Table
Write-Host "Share the setup .exe above."
