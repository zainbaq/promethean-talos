@echo off
call "%~dp0pyrun.cmd" "%~dp0run.py" %*
exit /b %ERRORLEVEL%
