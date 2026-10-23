@rem @ Project            : NAO Robot Inspection Toolbox
@rem @ Description        : Build the Windows executable
@rem @ Author             : XCrane
@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1" %*
exit /b %ERRORLEVEL%
