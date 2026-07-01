@echo off
REM ============================================================
REM  Build a SINGLE, SHAREABLE Athan.exe  (run this on Windows)
REM  Output:  dist\Athan.exe              <- send this one file
REM           dist\Athan-Share.zip        <- exe + README, ready to email
REM ============================================================

echo Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install requests winsdk pyinstaller

echo.
echo Building Athan.exe (standalone, no console window)...
REM No config is bundled on purpose: the recipient gets the first-run
REM "auto-detect my location" setup the first time they open it.
REM --collect-all winsdk: PyInstaller can't auto-find winsdk's lazy submodules,
REM so bundle them all (needed for Windows GPS location).
pyinstaller --onefile --noconsole --name Athan ^
  --collect-all requests --collect-all winsdk athan.py

if not exist dist\Athan.exe (
  echo BUILD FAILED - see messages above.
  pause
  exit /b 1
)

echo.
echo Packaging a share zip (exe + README)...
copy /Y README.md dist\README.md >nul 2>&1
if exist athan.wav copy /Y athan.wav dist\athan.wav >nul 2>&1
powershell -NoProfile -Command ^
  "Compress-Archive -Path 'dist\Athan.exe','dist\README.md' -DestinationPath 'dist\Athan-Share.zip' -Force"

echo.
echo ============================================================
echo  DONE.
echo  Send this single file:   dist\Athan.exe
echo  Or this zip:             dist\Athan-Share.zip
echo.
echo  The recipient just double-clicks Athan.exe. On first run it
echo  offers to auto-detect their city. Nothing to install.
echo ============================================================
pause
