@echo off
setlocal EnableExtensions
rem Checkout-local CLI. Uses this clone's src, not a pip/site-packages install.
rem Do not honor CURSOR_PLUGIN_ROOT: that can be an older marketplace cache.
set "TALMUDIC_SRC=%~dp0src"
if not exist "%TALMUDIC_SRC%\talmudic_memory\__init__.py" (
  echo TALMUDIC: expected src\talmudic_memory next to this launcher. Run it from the plugin clone root. 1>&2
  exit /b 1
)
set "PYTHONPATH=%TALMUDIC_SRC%"
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  py -3 -m talmudic_memory.cli %*
  exit /b %ERRORLEVEL%
)
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  python -m talmudic_memory.cli %*
  exit /b %ERRORLEVEL%
)
where python3 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  python3 -m talmudic_memory.cli %*
  exit /b %ERRORLEVEL%
)
echo TALMUDIC: Python 3.10+ not found. Install Python and ensure python or py -3 is on PATH. 1>&2
exit /b 1
