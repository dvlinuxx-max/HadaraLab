<#
Build the Microsoft Store package (MSIX) of HadaraLab in one step.

    powershell -ExecutionPolicy Bypass -File build_store.ps1
    powershell -ExecutionPolicy Bypass -File build_store.ps1 -SkipTests

Steps: run the tests, build the program with PyInstaller, put it next to the
manifest and logos in packaging\msix, stamp the version from hadaralab\__init__.py,
and pack store\HadaraLab_<version>_x64.msix with makeappx from the Windows SDK.
The package is unsigned; the Store signs it after upload.
#>
param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

# version: "1.0.2" in hadaralab\__init__.py -> "1.0.2.0" for the package
$init = Get-Content (Join-Path $root "hadaralab\__init__.py") -Raw
if ($init -notmatch '__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"') {
    throw "Could not read __version__ from hadaralab\__init__.py"
}
$version = "$($Matches[1]).$($Matches[2]).$($Matches[3]).0"
Write-Host "HadaraLab $version" -ForegroundColor Cyan

# makeappx.exe from the newest Windows SDK
$makeappx = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\makeappx.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeappx) {
    throw "makeappx.exe not found. Install the Windows 10/11 SDK."
}

if (-not $SkipTests) {
    Write-Host "Running the engine tests..."
    python tests\test_engine.py
    if ($LASTEXITCODE -ne 0) { throw "Engine tests failed." }
}

Write-Host "Building with PyInstaller..."
python -m PyInstaller HadaraLab.spec --noconfirm --log-level WARN
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

# package layout: the built program + manifest + logos
$layout = Join-Path $root "build\msix_layout"
if (Test-Path $layout) { Remove-Item $layout -Recurse -Force }
New-Item -ItemType Directory -Path $layout | Out-Null
Copy-Item (Join-Path $root "dist\HadaraLab\*") $layout -Recurse
Copy-Item (Join-Path $root "packaging\msix\Assets") $layout -Recurse

$manifest = Get-Content (Join-Path $root "packaging\msix\AppxManifest.xml") -Raw
$manifest = $manifest -replace '(<Identity[^>]*\sVersion=")[^"]+(")', "`${1}$version`${2}"
[System.IO.File]::WriteAllText((Join-Path $layout "AppxManifest.xml"), $manifest, (New-Object System.Text.UTF8Encoding $false))

$out = Join-Path $root "store"
New-Item -ItemType Directory -Path $out -Force | Out-Null
$msix = Join-Path $out "HadaraLab_$($version)_x64.msix"

Write-Host "Packing $msix ..."
& $makeappx.FullName pack /d $layout /p $msix /o | Select-Object -Last 1
if ($LASTEXITCODE -ne 0) { throw "makeappx failed." }

$size = [math]::Round((Get-Item $msix).Length / 1MB, 1)
Write-Host "Done: $msix ($size MB)" -ForegroundColor Green
