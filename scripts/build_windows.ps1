[CmdletBinding()]
param(
    [string]$PythonExecutable = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SpecFile = Join-Path $ProjectRoot "packaging\serialscope_windows.spec"
$WorkDirectory = Join-Path $ProjectRoot "build\SerialScope-Windows"
$DistRoot = Join-Path $ProjectRoot "dist"
$BundleDirectory = Join-Path $DistRoot "SerialScope"
$Executable = Join-Path $BundleDirectory "SerialScope.exe"
$BundledIcon = Join-Path $BundleDirectory "_internal\assets\icons\serialscope.png"

# Prevent host-level Python configuration from contaminating dependency analysis.
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue

function Fail-Build([string]$Message) {
    throw "SerialScope Windows build failed: $Message"
}

function Remove-GeneratedDirectory([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $Resolved = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path)
    $RootPrefix = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd("\") + "\"
    if (-not $Resolved.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        Fail-Build "refusing to remove a directory outside the repository: $Resolved"
    }
    Remove-Item -LiteralPath $Resolved -Recurse -Force
}

if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
} elseif (-not [System.IO.Path]::IsPathRooted($PythonExecutable)) {
    $PythonExecutable = Join-Path $ProjectRoot $PythonExecutable
}
$PythonExecutable = [System.IO.Path]::GetFullPath($PythonExecutable)

if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    Fail-Build "project Python environment not found: $PythonExecutable`nCreate it and install: python -m pip install -e `".[dev,packaging]`""
}
if (-not (Test-Path -LiteralPath $SpecFile -PathType Leaf)) {
    Fail-Build "Windows spec not found: $SpecFile"
}

& $PythonExecutable --version
if ($LASTEXITCODE -ne 0) {
    Fail-Build "Python environment is not usable: $PythonExecutable"
}

$PyInstallerVersion = & $PythonExecutable -c "import PyInstaller; print(PyInstaller.__version__)"
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($PyInstallerVersion)) {
    Fail-Build "PyInstaller is missing. Install with: python -m pip install -e `".[dev,packaging]`""
}

Remove-GeneratedDirectory $WorkDirectory
Remove-GeneratedDirectory $BundleDirectory

$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
Push-Location $ProjectRoot
try {
    & $PythonExecutable -m PyInstaller `
        --noconfirm `
        --clean `
        --workpath $WorkDirectory `
        --distpath $DistRoot `
        $SpecFile
    if ($LASTEXITCODE -ne 0) {
        Fail-Build "PyInstaller exited with code $LASTEXITCODE"
    }
} finally {
    Pop-Location
    $Stopwatch.Stop()
}

if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    Fail-Build "expected executable was not created: $Executable"
}
if (-not (Test-Path -LiteralPath $BundledIcon -PathType Leaf)) {
    Fail-Build "runtime application icon was not bundled: $BundledIcon"
}
$WindowsPlatformPlugin = Get-ChildItem -LiteralPath $BundleDirectory -Recurse -File -Filter "qwindows.dll" | Select-Object -First 1
if ($null -eq $WindowsPlatformPlugin) {
    Fail-Build "Qt's qwindows.dll platform plugin was not bundled"
}

$BundleBytes = (Get-ChildItem -LiteralPath $BundleDirectory -Recurse -File | Measure-Object -Property Length -Sum).Sum
$ExecutableBytes = (Get-Item -LiteralPath $Executable).Length
Write-Output "PyInstaller version: $PyInstallerVersion"
Write-Output ("Build duration: {0:N1} seconds" -f $Stopwatch.Elapsed.TotalSeconds)
Write-Output "SerialScope Windows bundle created at: $BundleDirectory"
Write-Output ("Bundle size: {0:N0} bytes" -f $BundleBytes)
Write-Output ("SerialScope.exe size: {0:N0} bytes" -f $ExecutableBytes)
Write-Output "Qt Windows platform plugin: $($WindowsPlatformPlugin.FullName)"
