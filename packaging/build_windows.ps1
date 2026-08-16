# Build SlideAnnotator.exe and wrap it in an Inno Setup installer.
#
# Usage: pwsh -File packaging/build_windows.ps1
#
# StarDist nuclei detection is unavailable on Windows: its NMS extension is a
# prebuilt macOS/arm64 binary. The app degrades with a message (see
# slideannotator/inference/nms.py).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$initFile = Join-Path $root "slideannotator\__init__.py"
$version = ([regex]::Match((Get-Content $initFile -Raw), '__version__ = "(.*)"')).Groups[1].Value
Write-Host "==> Building SlideAnnotator $version (win64)"

Write-Host "==> Rendering icons"
uv run python packaging/make_icons.py

Write-Host "==> Running PyInstaller"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
uv run pyinstaller packaging/slideannotator.spec --noconfirm

Write-Host "==> Verifying the frozen build"
& "dist\SlideAnnotator\SlideAnnotator.exe" --self-test
if ($LASTEXITCODE -ne 0) { throw "self-test failed" }

Write-Host "==> Building installer"
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "iscc" }
& $iscc "/DMyAppVersion=$version" "packaging\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

Get-ChildItem dist\*.exe | ForEach-Object {
    Write-Host ("Built {0} ({1:N0} MB)" -f $_.Name, ($_.Length / 1MB))
}
