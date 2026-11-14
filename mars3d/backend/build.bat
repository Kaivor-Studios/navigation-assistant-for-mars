@echo off
REM Build the NAM C++ terrain cruncher as a Windows DLL for ctypes.
REM Requires a C++ compiler on PATH. Easiest: install MinGW-w64
REM   (https://www.mingw-w64.org/) or via MSYS2:  pacman -S mingw-w64-ucrt-x86_64-gcc
REM Then run this script from the backend\ folder:
REM   build.bat
REM Produces terrain.dll, which cruncher.py loads automatically on Windows.
REM
REM If you do NOT have a compiler, skip this entirely: the server runs fine on
REM the pure-Python/numpy fallback (slower but fully functional). See README.md.

where g++ >nul 2>nul
if errorlevel 1 (
  echo [build.bat] g++ not found on PATH.
  echo   Install MinGW-w64 (https://www.mingw-w64.org/) or MSYS2, then re-run.
  echo   Or skip this: the server works without the DLL via the numpy fallback.
  exit /b 1
)

g++ -O3 -shared -o terrain.dll terrain.cpp
if errorlevel 1 (
  echo [build.bat] compilation failed.
  exit /b 1
)
echo Built terrain.dll
dir terrain.dll | findstr terrain.dll
