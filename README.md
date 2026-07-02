<h1 align="center">☪ Athan</h1>
<p align="center">Prayer times for Windows — a quiet reminder to pray, right on your desktop.</p>

<p align="center">
  <a href="https://github.com/bo3lwaq8/Athan/releases/latest/download/Athan.exe">
    <img src="https://img.shields.io/badge/%E2%AC%87%20Download-Athan.exe-2ea44f?style=for-the-badge&logo=windows&logoColor=white" alt="Download Athan.exe">
  </a>
  &nbsp;
  <a href="https://github.com/bo3lwaq8/Athan/releases/latest">
    <img src="https://img.shields.io/github/v/release/bo3lwaq8/Athan?style=for-the-badge&label=version&color=1b263b" alt="Latest version">
  </a>
</p>

---

## Features

- **Daily prayer times** for your location — auto-detected or searched by city.
- **15-minute warning** before each prayer.
- **Athan reminder** at prayer time: a fullscreen overlay with audio, plus a screen
  lock that stays until you mark your prayer as finished.
- **Post-prayer dhikr** reminders.
- Multiple **calculation methods** with high-latitude support.
- **Starts with Windows** and **updates itself** automatically.

## Download

Get the latest **[Athan.exe](https://github.com/bo3lwaq8/Athan/releases/latest/download/Athan.exe)** — no installation needed. Double-click to run; on first launch it offers to detect your location.

> The app is unsigned, so Windows SmartScreen may warn on first run. Choose **More info → Run anyway**. Settings are saved in a `config.json` created next to the app.

## Build from source

Requires Python 3.10+ on Windows.

```bat
pip install -r requirements.txt
python athan.py        REM run directly
build.bat              REM or build a standalone dist\Athan.exe
```

## License

Free to use and modify.
