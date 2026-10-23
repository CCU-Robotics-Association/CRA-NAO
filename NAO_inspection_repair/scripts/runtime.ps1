# -*- coding: utf-8 -*-
<#
@ Project            : NAO 机器人验修工具箱
@ Description        : 启动与打包共用的 Python 和 SDK 查找
@ Author             : XCrane
#>

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
    if ($Explicit) {
        if (-not (Test-Path -LiteralPath $Explicit -PathType Leaf)) {
            throw 'The specified Python executable does not exist.'
        }
        $version = & $Explicit -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne '2.7') {
            throw 'The specified Python executable must be Python 2.7.'
        }
        return (Resolve-Path -LiteralPath $Explicit).Path
    }
    $candidates = @()
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

function Find-SdkLib {
    param([string]$Explicit, [string]$PythonExe)
    if ($Explicit) {
        $resolved = Resolve-SdkLib -Candidate $Explicit
        if (-not $resolved) { throw 'The specified SDK directory does not contain naoqi.py.' }
        return $resolved
    }
    $resolved = Resolve-SdkLib -Candidate $env:PYNAOQI_SDK
    if ($resolved) { return $resolved }
    $pth = Join-Path (Split-Path $PythonExe -Parent) 'Lib\site-packages\naoqi_sdk.pth'
    if (Test-Path -LiteralPath $pth) {
        foreach ($line in Get-Content -LiteralPath $pth) {
            $resolved = Resolve-SdkLib -Candidate $line.Trim()
            if ($resolved) { return $resolved }
        }
    }
    if (Test-Path -LiteralPath 'P:\NAO') {
        $found = Get-ChildItem -LiteralPath 'P:\NAO' -Filter 'naoqi.py' -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.Directory.Name -eq 'lib' } |
            Select-Object -First 1
        if ($found) { return $found.Directory.FullName }
    }
    return $null
}
