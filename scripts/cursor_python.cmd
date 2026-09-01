: <<':BAT'
@echo off
setlocal EnableExtensions
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  py -3 %*
  exit /b %ERRORLEVEL%
)
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  python %*
  exit /b %ERRORLEVEL%
)
where python3 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  python3 %*
  exit /b %ERRORLEVEL%
)
echo TALMUDIC: Python 3.10+ not found. Install Python and ensure python or py -3 is on PATH. 1>&2
exit /b 1
:BAT
_win=0
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) _win=1 ;;
esac
if [ -n "${WINDIR-}" ] || [ -n "${SYSTEMROOT-}" ]; then
  _win=1
fi
if [ "$_win" = 1 ]; then
  if command -v py >/dev/null 2>&1; then
    exec py -3 "$@"
  fi
  if command -v python >/dev/null 2>&1; then
    exec python "$@"
  fi
  if command -v python3 >/dev/null 2>&1; then
    exec python3 "$@"
  fi
else
  if command -v python3 >/dev/null 2>&1; then
    exec python3 "$@"
  fi
  if command -v python >/dev/null 2>&1; then
    exec python "$@"
  fi
  if command -v py >/dev/null 2>&1; then
    exec py -3 "$@"
  fi
fi
echo "TALMUDIC: Python 3.10+ not found. Install Python and ensure python or py -3 is on PATH." >&2
exit 1
