param(
    [string]$MpvCoreDir = $env:MPV_CORE_DIR,
    [string]$FfmpegBinDir = $env:FFMPEG_BIN_DIR,
    [string]$IsccPath = $env:INNO_SETUP_COMPILER
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

if (-not $MpvCoreDir) {
    throw 'Set MPV_CORE_DIR or pass -MpvCoreDir (directory containing Yaoplayer.com).'
}
if (-not $FfmpegBinDir) {
    throw 'Set FFMPEG_BIN_DIR or pass -FfmpegBinDir (directory containing ffmpeg.exe and ffprobe.exe).'
}
if (-not $IsccPath) {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe')
    )
    $IsccPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $IsccPath -or -not (Test-Path -LiteralPath $IsccPath)) {
    throw 'Inno Setup 7 ISCC.exe not found. Pass -IsccPath or set INNO_SETUP_COMPILER.'
}

$mpv = Join-Path $MpvCoreDir 'Yaoplayer.com'
$ffmpeg = Join-Path $FfmpegBinDir 'ffmpeg.exe'
$ffprobe = Join-Path $FfmpegBinDir 'ffprobe.exe'
foreach ($required in @($mpv, $ffmpeg, $ffprobe)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required tool not found: $required" }
}

$python = Get-Command python -ErrorAction Stop
$dist = Join-Path $root 'build\app'
$work = Join-Path $root 'build\pyinstaller'
$spec = Join-Path $root 'build\spec'
$null = New-Item -ItemType Directory -Force -Path $dist, $work, $spec

$pyArgs = @(
    '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
    '--name', '声匣缓存转换器',
    '--distpath', $dist,
    '--workpath', $work,
    '--specpath', $spec,
    '--icon', (Join-Path $root 'assets\shengxia.ico'),
    '--add-data', "$MpvCoreDir;tools/mpv",
    '--add-data', "$ffmpeg;tools/ffmpeg",
    '--add-data', "$ffprobe;tools/ffmpeg",
    (Join-Path $root 'gui.py')
)
& $python.Source @pyArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

& $IsccPath (Join-Path $root 'installer\shengxia.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }

Write-Host "Installer created: $(Join-Path $root 'artifacts\ShengXiaCacheConverter-Setup-0.1.0-x64.exe')"
