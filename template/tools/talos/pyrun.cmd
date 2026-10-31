@echo off
rem pyrun.cmd: run a Python script with the project's own interpreter (see pyrun).
set "ROOT=%~dp0..\.."
if exist "%ROOT%\.venv\Scripts\python.exe" (
  "%ROOT%\.venv\Scripts\python.exe" %*
  exit /b %ERRORLEVEL%
)
if defined TALOS_PYTHON (
  "%TALOS_PYTHON%" %*
  exit /b %ERRORLEVEL%
)
py -3 -c "" >nul 2>&1 && (
  py -3 %*
  exit /b %ERRORLEVEL%
)
python -c "" >nul 2>&1 && (
  python %*
  exit /b %ERRORLEVEL%
)
uv --version >nul 2>&1 && (
  uv run --no-project python %*
  exit /b %ERRORLEVEL%
)
echo pyrun: no working Python found. Install uv (winget install astral-sh.uv) or set TALOS_PYTHON. 1>&2
exit /b 127
