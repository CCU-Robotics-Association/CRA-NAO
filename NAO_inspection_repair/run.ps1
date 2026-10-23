# -*- coding: utf-8 -*-
<#
@ Project            : NAO 机器人验修工具箱
@ Description        : 解析启动参数并运行验收程序
@ Author             : XCrane
#>

param(
    [string[]]$Ip,
    [int]$Port = 9559,
    [string]$RobotId,
    [string]$Inventory,
    [ValidateSet('quick', 'guided', 'full')]
    [string]$Profile = 'quick',
    [string]$Output = 'reports',
    [string]$Config,
    [switch]$NonInteractive,
    [switch]$NoVoice,
    [ValidateSet('auto', 'Chinese', 'English')]
    [string]$Language = 'auto',
    [switch]$AllowMotion,
    [switch]$AllowWalk,
    [switch]$AssumeYes,
    [string]$Only,
    [string]$Skip,
    [switch]$CollectLogs,
    [string]$SshUser = 'nao',
    [int]$SshPort = 22,
    [string]$SshKey,
    [string[]]$LogDir,
    [switch]$ListTests,
    [switch]$Gui,
    [switch]$Detailed,
    [string]$PythonExe,
    [string]$SdkRoot,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'

. (Join-Path $PSScriptRoot 'scripts\runtime.ps1')

$python = Find-Python27 -Explicit $PythonExe
if (-not $python) {
    throw 'Compatible Python 2.7 was not found. Use -PythonExe to specify python.exe.'
}

$sdkLib = Find-SdkLib -Explicit $SdkRoot -PythonExe $python

$needSdk = $Gui -or -not $ListTests
if (-not $sdkLib -and $needSdk) {
    throw 'pynaoqi SDK was not found. Use -SdkRoot to specify its root or lib directory.'
}
if ($sdkLib) {
    if ($env:PYTHONPATH) { $env:PYTHONPATH = "$sdkLib;$($env:PYTHONPATH)" } else { $env:PYTHONPATH = $sdkLib }
    $env:PATH = "$sdkLib;$($env:PATH)"
}

$pythonRoot = Split-Path $python -Parent
$tclLibrary = Join-Path $pythonRoot 'tcl\tcl8.5'
$tkLibrary = Join-Path $pythonRoot 'tcl\tk8.5'
if (Test-Path -LiteralPath (Join-Path $tclLibrary 'init.tcl')) { $env:TCL_LIBRARY = $tclLibrary }
if (Test-Path -LiteralPath (Join-Path $tkLibrary 'tk.tcl')) { $env:TK_LIBRARY = $tkLibrary }

if ($Gui) {
    Write-Host "Python: $python"
    if ($sdkLib) { Write-Host "pynaoqi SDK: $sdkLib" }
    & $python -B (Join-Path $PSScriptRoot 'nao_gui.py')
    exit $LASTEXITCODE
}

$arguments = @()
foreach ($address in $Ip) { if ($address) { $arguments += @('--ip', $address) } }
$arguments += @('--port', $Port, '--profile', $Profile, '--output', $Output, '--language', $Language)
if ($RobotId) { $arguments += @('--robot-id', $RobotId) }
if ($Inventory) { $arguments += @('--inventory', $Inventory) }
if ($Config) { $arguments += @('--config', $Config) }
if ($NonInteractive) { $arguments += '--non-interactive' }
if ($NoVoice) { $arguments += '--no-voice' }
if ($AllowMotion) { $arguments += '--allow-motion' }
if ($AllowWalk) { $arguments += '--allow-walk' }
if ($AssumeYes) { $arguments += '--assume-yes' }
if ($Only) { $arguments += @('--only', $Only) }
if ($Skip) { $arguments += @('--skip', $Skip) }
if ($CollectLogs) { $arguments += '--collect-logs' }
if ($SshUser) { $arguments += @('--ssh-user', $SshUser) }
if ($SshPort) { $arguments += @('--ssh-port', $SshPort) }
if ($SshKey) { $arguments += @('--ssh-key', $SshKey) }
foreach ($directory in $LogDir) { if ($directory) { $arguments += @('--log-dir', $directory) } }
if ($ListTests) { $arguments += '--list-tests' }
if ($Detailed) { $arguments += '--verbose' }
if ($ExtraArgs) { $arguments += $ExtraArgs }

Write-Host "Python: $python"
if ($sdkLib) { Write-Host "pynaoqi SDK: $sdkLib" }
& $python -B (Join-Path $PSScriptRoot 'nao_diagnostic.py') @arguments
exit $LASTEXITCODE
