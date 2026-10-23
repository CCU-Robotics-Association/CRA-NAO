# -*- coding: utf-8 -*-
<#
@ Project            : NAO 机器人验修工具箱
@ Description        : 检查构建环境并打包 Windows EXE
@ Author             : XCrane
#>

param(
    [string]$PythonExe,
    [string]$SdkRoot,
    [switch]$Clean,
    [switch]$RequireSignature
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

. (Join-Path $PSScriptRoot 'scripts\runtime.ps1')

$python = Find-Python27 -Explicit $PythonExe
if (-not $python) { throw 'Compatible Python 2.7 was not found. Use -PythonExe.' }

& $python -B (Join-Path $PSScriptRoot 'scripts\build_metadata.py')
if ($LASTEXITCODE -ne 0) {
    throw 'Build tools differ from the lock files. Install packaging/requirements-bootstrap.lock and requirements-build.txt in a dedicated build environment.'
}

$sdkLib = Find-SdkLib -Explicit $SdkRoot -PythonExe $python
if (-not $sdkLib) { throw 'pynaoqi SDK was not found. Use -SdkRoot.' }

$pythonRoot = Split-Path $python -Parent
$tclLibrary = Join-Path $pythonRoot 'tcl\tcl8.5'
$tkLibrary = Join-Path $pythonRoot 'tcl\tk8.5'
if (Test-Path -LiteralPath (Join-Path $tclLibrary 'init.tcl')) { $env:TCL_LIBRARY = $tclLibrary }
if (Test-Path -LiteralPath (Join-Path $tkLibrary 'tk.tcl')) { $env:TK_LIBRARY = $tkLibrary }
$env:PYNAOQI_SDK = $sdkLib
$env:PYTHONPATH = $sdkLib
$env:PATH = "$sdkLib;$($env:PATH)"

& $python -c "import Tkinter as tk; root=tk.Tk(); root.withdraw(); root.update(); root.destroy(); print('Tkinter OK')"
if ($LASTEXITCODE -ne 0) {
    throw 'Tkinter cannot create a window. Repair or recreate the Python 2.7 x64 environment before packaging.'
}

$pyInstallerVersion = & $python -c "import PyInstaller; print(PyInstaller.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is not installed. Run: python -m pip install -r requirements-build.txt'
}
if ($pyInstallerVersion.Trim() -ne '3.6') {
    throw ("PyInstaller 3.6 is required for Python 2.7; found " + $pyInstallerVersion.Trim())
}
Write-Host ("PyInstaller: " + $pyInstallerVersion.Trim())

Push-Location $PSScriptRoot
try {
    $buildArguments = @('-B', '-m', 'PyInstaller', '--noconfirm')
    if ($Clean) { $buildArguments += '--clean' }
    $buildArguments += (Join-Path $PSScriptRoot 'nao_toolbox.spec')
    & $python @buildArguments
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host ''
$executable = Join-Path $PSScriptRoot 'dist\NAO_Toolbox.exe'
$runtimeReport = Join-Path $PSScriptRoot ('build\runtime-check-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
$check = Start-Process -FilePath $executable -ArgumentList @('--check-runtime', ('"' + $runtimeReport + '"')) -WindowStyle Hidden -PassThru
if (-not $check.WaitForExit(90000)) {
    throw 'The packaged runtime check did not finish within 90 seconds.'
}
if ($check.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $runtimeReport)) {
    throw ('The packaged runtime check failed. See ' + $runtimeReport)
}
$runtime = Get-Content -LiteralPath $runtimeReport -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $runtime.ok -or -not $runtime.frozen) {
    throw ('The packaged runtime is incomplete. See ' + $runtimeReport)
}
Write-Host 'Packaged Python, NAOqi SDK and Tkinter checks passed.'
Write-Host ("Build complete: " + $executable)
Write-Host 'The bundled NAOqi SDK is large, so one-file startup may take a while.'
$signature = Get-AuthenticodeSignature -FilePath $executable
if ($signature.Status -ne 'Valid') {
    if ($RequireSignature) { throw 'A trusted Authenticode signature is required. No release archive was created.' }
    Write-Warning 'This executable has no trusted Authenticode signature. SHA256 metadata does not replace publisher signing.'
}

$releaseRoot = Join-Path $PSScriptRoot 'release'
$versionSource = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'nao_diag\__init__.py'))
$toolVersion = [regex]::Match($versionSource, '__version__\s*=\s*"([^"]+)"').Groups[1].Value
if (-not $toolVersion) { throw 'The application version is missing.' }
$releaseName = 'NAO_Toolbox-' + $toolVersion + '-win64'
$packageDir = Join-Path $releaseRoot $releaseName
New-Item -ItemType Directory -Path $packageDir -Force | Out-Null
Copy-Item -LiteralPath $executable -Destination (Join-Path $packageDir 'NAO_Toolbox.exe') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'config.example.json') -Destination $packageDir -Force
$usageFiles = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'packaging') -Filter '*.txt' -File |
    Where-Object { $_.Name -ne 'UNIX_USAGE.txt' })
if ($usageFiles.Count -ne 1) { throw 'Exactly one Windows release usage document is required.' }
Copy-Item -LiteralPath $usageFiles[0].FullName -Destination $packageDir -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'docs') -Destination $packageDir -Recurse -Force
$archive = Join-Path $releaseRoot ($releaseName + '.zip')
Compress-Archive -LiteralPath $packageDir -DestinationPath $archive -Force
& $python -B (Join-Path $PSScriptRoot 'scripts\build_metadata.py') --archive $archive --signing ($signature.Status.ToString())
if ($LASTEXITCODE -ne 0) { throw 'Release metadata generation failed; do not publish this archive.' }
Write-Host ('Release package: ' + $archive)
