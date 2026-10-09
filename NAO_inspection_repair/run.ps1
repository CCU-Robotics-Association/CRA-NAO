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
    [switch]$DemoReport,
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

function Resolve-SdkLib {
    param([string]$Candidate)
    if (-not $Candidate) { return $null }
    $expanded = [Environment]::ExpandEnvironmentVariables($Candidate)
    if (Test-Path -LiteralPath (Join-Path $expanded 'naoqi.py')) {
        return (Resolve-Path -LiteralPath $expanded).Path
    }
    if (Test-Path -LiteralPath (Join-Path $expanded 'lib\naoqi.py')) {
        return (Resolve-Path -LiteralPath (Join-Path $expanded 'lib')).Path
    }
    return $null
}

function Find-Python27 {
    param([string]$Explicit)
    $candidates = @()
    if ($Explicit) { $candidates += $Explicit }
    if ($env:CONDA_PREFIX) { $candidates += (Join-Path $env:CONDA_PREFIX 'python.exe') }
    $candidates += (Join-Path $env:USERPROFILE '.conda\envs\NAO\python.exe')
    $candidates += 'P:\Anaconda\Anaconda3\envs\NAO\python.exe'
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-Path -LiteralPath $candidate) {
            $version = & $candidate -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version.Trim() -eq '2.7') {
                return (Resolve-Path -LiteralPath $candidate).Path
            }
        }
    }
    $conda = Get-Command conda -ErrorAction SilentlyContinue
    if ($conda) {
        try {
            $envInfo = (& $conda.Source env list --json | ConvertFrom-Json)
            foreach ($prefix in $envInfo.envs) {
                if ((Split-Path $prefix -Leaf) -ieq 'NAO') {
                    $candidate = Join-Path $prefix 'python.exe'
                    if (Test-Path -LiteralPath $candidate) { return $candidate }
                }
            }
        } catch { }
    }
    return $null
}

$python = Find-Python27 -Explicit $PythonExe
if (-not $python) {
    throw 'Compatible Python 2.7 was not found. Use -PythonExe to specify python.exe.'
}

$sdkLib = Resolve-SdkLib -Candidate $SdkRoot
if (-not $sdkLib) { $sdkLib = Resolve-SdkLib -Candidate $env:PYNAOQI_SDK }
if (-not $sdkLib) {
    $pth = Join-Path (Split-Path $python -Parent) 'Lib\site-packages\naoqi_sdk.pth'
    if (Test-Path -LiteralPath $pth) {
        foreach ($line in Get-Content -LiteralPath $pth) {
            $sdkLib = Resolve-SdkLib -Candidate $line.Trim()
            if ($sdkLib) { break }
        }
    }
}
if (-not $sdkLib -and (Test-Path -LiteralPath 'P:\NAO')) {
    $found = Get-ChildItem -LiteralPath 'P:\NAO' -Filter 'naoqi.py' -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq 'lib' } |
        Select-Object -First 1
    if ($found) { $sdkLib = $found.Directory.FullName }
}

$needSdk = -not ($ListTests -or $DemoReport)
if (-not $sdkLib -and $needSdk) {
    throw 'pynaoqi SDK was not found. Use -SdkRoot to specify its root or lib directory.'
}
if ($sdkLib) {
    if ($env:PYTHONPATH) { $env:PYTHONPATH = "$sdkLib;$($env:PYTHONPATH)" } else { $env:PYTHONPATH = $sdkLib }
    $env:PATH = "$sdkLib;$($env:PATH)"
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
if ($DemoReport) { $arguments += '--demo-report' }
if ($Detailed) { $arguments += '--verbose' }
if ($ExtraArgs) { $arguments += $ExtraArgs }

Write-Host "Python: $python"
if ($sdkLib) { Write-Host "pynaoqi SDK: $sdkLib" }
& $python -B (Join-Path $PSScriptRoot 'nao_diagnostic.py') @arguments
exit $LASTEXITCODE
