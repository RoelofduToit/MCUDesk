[CmdletBinding()]
param(
    [string]$IsccPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$VersionFile = Join-Path $ProjectRoot "src\serialscope\__init__.py"
$InstallerScript = Join-Path $ProjectRoot "packaging\windows\serialscope.iss"
$BundleExe = Join-Path $ProjectRoot "dist\SerialScope\SerialScope.exe"
$InstallerDir = Join-Path $ProjectRoot "dist\installer"

function Fail-Build([string]$Message) {
    throw "SerialScope installer build failed: $Message"
}

if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
    Fail-Build "version file not found: $VersionFile"
}

$VersionText = Get-Content -LiteralPath $VersionFile -Raw

$Match = [regex]::Match(
    $VersionText,
    '__version__\s*=\s*"([^"]+)"'
)

if (-not $Match.Success) {
    Fail-Build "could not read serialscope.__version__"
}

$Version = $Match.Groups[1].Value

if (-not (Test-Path -LiteralPath $InstallerScript -PathType Leaf)) {
    Fail-Build "Inno Setup script not found: $InstallerScript"
}

if (-not (Test-Path -LiteralPath $BundleExe -PathType Leaf)) {
    Fail-Build "Windows bundle not found: $BundleExe`nRun scripts\build_windows.ps1 first."
}

if ([string]::IsNullOrWhiteSpace($IsccPath)) {
    $Candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )

    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
            $IsccPath = $Candidate
            break
        }
    }
}

if ([string]::IsNullOrWhiteSpace($IsccPath) -or
    -not (Test-Path -LiteralPath $IsccPath -PathType Leaf)) {
    Fail-Build "ISCC.exe not found. Install Inno Setup or provide -IsccPath."
}

New-Item -ItemType Directory -Force -Path $InstallerDir | Out-Null

$ExpectedInstaller = Join-Path `
    $InstallerDir `
    "SerialScope_${Version}_Windows_x64_Setup.exe"

if (Test-Path -LiteralPath $ExpectedInstaller) {
    Remove-Item -LiteralPath $ExpectedInstaller -Force
}

Write-Output "SerialScope version: $Version"
Write-Output "Inno Setup compiler: $IsccPath"

Push-Location $ProjectRoot

try {
    & $IsccPath "/DAppVersion=$Version" $InstallerScript

    if ($LASTEXITCODE -ne 0) {
        Fail-Build "ISCC exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $ExpectedInstaller -PathType Leaf)) {
    Fail-Build "expected installer was not created: $ExpectedInstaller"
}

$Installer = Get-Item -LiteralPath $ExpectedInstaller
$Hash = Get-FileHash -LiteralPath $ExpectedInstaller -Algorithm SHA256

Write-Output ""
Write-Output "Windows installer created successfully."
Write-Output "Path: $($Installer.FullName)"
Write-Output ("Size: {0:N2} MiB" -f ($Installer.Length / 1MB))
Write-Output "SHA256: $($Hash.Hash)"