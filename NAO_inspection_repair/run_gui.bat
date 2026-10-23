@rem @ Project            : NAO Robot Inspection Toolbox
@rem @ Description        : Launch the inspection GUI
@rem @ Author             : XCrane
@echo off
setlocal
call "%~dp0run.bat" -Gui %*
exit /b %ERRORLEVEL%
