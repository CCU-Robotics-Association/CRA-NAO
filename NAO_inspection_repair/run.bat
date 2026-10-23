@rem @ Project            : NAO Robot Inspection Toolbox
@rem @ Description        : Launch command-line inspection
@rem @ Author             : XCrane
@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
exit /b %ERRORLEVEL%
