[CmdletBinding()]
param(
    [ValidateRange(1, 30)]
    [int]$StartupSeconds = 3
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Executable = Join-Path $ProjectRoot "dist\MCUDesk\MCUDesk.exe"
$BundledIcon = Join-Path $ProjectRoot "dist\MCUDesk\_internal\assets\icons\mcudesk.png"
$SmokeDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("MCUDesk-smoke-" + [guid]::NewGuid().ToString("N"))
$Process = $null

function Fail-SmokeTest([string]$Message) {
    throw "MCUDesk Windows smoke test failed: $Message"
}

function Get-PeSubsystem([string]$Path) {
    $Stream = [System.IO.File]::OpenRead($Path)
    $Reader = [System.IO.BinaryReader]::new($Stream)
    try {
        $Stream.Position = 0x3c
        $PeOffset = $Reader.ReadInt32()
        $Stream.Position = $PeOffset
        if ($Reader.ReadUInt32() -ne 0x00004550) {
            Fail-SmokeTest "executable does not contain a valid PE signature"
        }
        $OptionalHeader = $PeOffset + 24
        $Stream.Position = $OptionalHeader + 68
        return $Reader.ReadUInt16()
    } finally {
        $Reader.Dispose()
        $Stream.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    Fail-SmokeTest "packaged executable not found: $Executable"
}
if (-not (Test-Path -LiteralPath $BundledIcon -PathType Leaf)) {
    Fail-SmokeTest "bundled runtime icon not found: $BundledIcon"
}
if ((Get-PeSubsystem $Executable) -ne 2) {
    Fail-SmokeTest "MCUDesk.exe is not a Windows GUI-subsystem executable"
}

Add-Type -AssemblyName System.Drawing
$AssociatedIcon = [System.Drawing.Icon]::ExtractAssociatedIcon($Executable)
if ($null -eq $AssociatedIcon) {
    Fail-SmokeTest "MCUDesk.exe does not expose an associated Windows icon"
}
$AssociatedIcon.Dispose()

New-Item -ItemType Directory -Path $SmokeDirectory | Out-Null
try {
    $Process = Start-Process `
        -FilePath $Executable `
        -WorkingDirectory $SmokeDirectory `
        -PassThru
    Start-Sleep -Seconds $StartupSeconds
    $Process.Refresh()
    if ($Process.HasExited) {
        Fail-SmokeTest "application exited during startup with code $($Process.ExitCode)"
    }

    $ClosedNormally = $Process.CloseMainWindow()
    if ($ClosedNormally) {
        $null = $Process.WaitForExit(5000)
    }
    Write-Output "Packaged MCUDesk remained alive for $StartupSeconds seconds from unrelated cwd: $SmokeDirectory"
    Write-Output "Windows GUI subsystem and embedded icon checks passed."
} finally {
    if ($null -ne $Process) {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force
            $Process.WaitForExit()
        }
        $Process.Dispose()
    }
    if (Test-Path -LiteralPath $SmokeDirectory) {
        Remove-Item -LiteralPath $SmokeDirectory -Recurse -Force
    }
}
