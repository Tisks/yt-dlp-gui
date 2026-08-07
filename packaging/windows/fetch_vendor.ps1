# Populates vendor/win/bin with the external tools the app ships.
# Windows builds of ffmpeg/deno are statically linked, so no lib/ step is needed.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # keeps Invoke-WebRequest fast in CI

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Vendor = Join-Path $ProjectRoot "vendor\win"
$BinDir = Join-Path $Vendor "bin"
$Work = Join-Path $env:TEMP "yt-dlp-gui-vendor"

if (Test-Path $Vendor) { Remove-Item -Recurse -Force $Vendor }
if (Test-Path $Work) { Remove-Item -Recurse -Force $Work }
New-Item -ItemType Directory -Force -Path $BinDir, $Work | Out-Null

Write-Host "Downloading yt-dlp..."
Invoke-WebRequest -UseBasicParsing `
  -Uri "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" `
  -OutFile (Join-Path $BinDir "yt-dlp.exe")

Write-Host "Downloading ffmpeg/ffprobe..."
$FfmpegZip = Join-Path $Work "ffmpeg.zip"
Invoke-WebRequest -UseBasicParsing `
  -Uri "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" `
  -OutFile $FfmpegZip
Expand-Archive -Path $FfmpegZip -DestinationPath (Join-Path $Work "ffmpeg") -Force
foreach ($tool in @("ffmpeg.exe", "ffprobe.exe")) {
  $found = Get-ChildItem -Path (Join-Path $Work "ffmpeg") -Filter $tool -Recurse | Select-Object -First 1
  if (-not $found) { throw "$tool not found in the ffmpeg archive" }
  Copy-Item $found.FullName (Join-Path $BinDir $tool)
}

Write-Host "Downloading deno..."
$DenoZip = Join-Path $Work "deno.zip"
Invoke-WebRequest -UseBasicParsing `
  -Uri "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip" `
  -OutFile $DenoZip
Expand-Archive -Path $DenoZip -DestinationPath (Join-Path $Work "deno") -Force
$deno = Get-ChildItem -Path (Join-Path $Work "deno") -Filter "deno.exe" -Recurse | Select-Object -First 1
if (-not $deno) { throw "deno.exe not found in the deno archive" }
Copy-Item $deno.FullName (Join-Path $BinDir "deno.exe")

Remove-Item -Recurse -Force $Work

Write-Host ""
Write-Host "Vendored into $BinDir :"
Get-ChildItem $BinDir | Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 1) } } | Format-Table

foreach ($required in @("yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe", "deno.exe")) {
  if (-not (Test-Path (Join-Path $BinDir $required))) { throw "Missing $required after fetch" }
}
Write-Host "All four tools present."
