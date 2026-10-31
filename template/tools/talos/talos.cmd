@echo off
call "%~dp0pyrun.cmd" "%~dp0talos.py" %*
exit /b %ERRORLEVEL%
