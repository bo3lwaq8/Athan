# Athan — Prayer Times Desktop App (Windows)

A simple desktop app that shows today's prayer times, warns you **15 minutes
before** each prayer, and when the athan time arrives shows a **fullscreen
overlay** (with athan audio) **and locks your Windows session**. After praying,
press **"I finished praying"** to dismiss — but that button only unlocks **5
minutes after the lockdown starts**, so the prayer time is respected.

Prayer times come from the free [Aladhan API](https://aladhan.com/prayer-times-api),
using the **Umm al-Qura (Makkah)** calculation method by default. It can
**auto-detect your location** and **start automatically with Windows**.

---

## Files

| File | Purpose |
|------|---------|
| `athan.py` | The whole app (UI + scheduler + lock/overlay). |
| `config.json` | Your settings (city, method, minutes-before, etc.). |
| `requirements.txt` | Python dependency (`requests`). |
| `build.bat` | One-click build that produces `dist\Athan.exe`. |
| `athan.wav` *(optional)* | Your own athan audio — place it next to the exe. |

---

## Option A — Run it right away (Python)

1. Install [Python 3.10+](https://www.python.org/downloads/) (check *"Add Python to PATH"*).
2. Open a terminal in this folder and run:
   ```
   pip install requests
   python athan.py
   ```

## Option B — Build the .exe and share it

> A Windows `.exe` must be built on Windows. Just double-click **`build.bat`**.

It installs `requests` + `pyinstaller`, then creates:

- **`dist\Athan.exe`** — one self-contained file, nothing to install.
- **`dist\Athan-Share.zip`** — the exe + README, ready to email.

### Shipping it to someone else

Just send them **`Athan.exe`** (or the zip). They double-click it — no Python,
no install, no `config.json` needed. On first launch it shows a welcome screen
offering **"Auto-detect my location,"** so they're set up in one click. Their
settings are saved in a `config.json` created next to the exe.

One thing to expect: the first time they run an unsigned exe, Windows
SmartScreen may say *"Windows protected your PC."* They click **More info →
Run anyway**. To remove that warning for good you'd need to code-sign the exe
(a paid certificate) — fine for personal sharing, worth it for wider release.

### Start automatically with Windows

Open **Settings** in the app and tick **"Start Athan when Windows starts."**
That writes a per-user startup entry for you (no admin needed); unticking it
removes the entry. You can still do it manually via `Win+R` → `shell:startup`
if you prefer.

---

## Using the app

- **Settings** — set City/Country or **auto-detect location**, pick the
  calculation method, set minutes-before-athan, set the **lock duration** before
  "I finished praying" unlocks, and toggle lock / overlay / audio / autostart.
- **Refresh** — re-pull today's times.
- **Test athan** — fire the overlay + lock immediately so you can see what it does.
- The card shows all five prayers; the top shows a live clock and a
  *"Next: Maghrib in 1h 12m"* countdown.

### At athan time

The overlay appears and plays the athan; a few seconds later the screen locks.
The **"I finished praying"** button stays greyed out with a live countdown
(*"You can mark prayer finished in 4:59"*) and only becomes clickable once the
lock duration (default **5 minutes**) has passed. Log back into Windows, and the
overlay is waiting on top — press the button to dismiss it. The countdown keeps
running while the screen is locked, so by the time you're back it's usually
ready.

**Athan audio:** drop a file named `athan.wav` next to `athan.py` (or
`Athan.exe`). If none is present it plays a short beep so you still get an
audible cue. (`winsound` plays `.wav` only — convert an mp3 to wav if needed.)

**Unlocking:** the device uses the normal Windows lock screen, so you log back
in with your usual PIN/password after praying.

---

## Notes & limitations

- The lock uses Windows' own `LockWorkStation()` — it is the standard, secure
  lock (same as `Win+L`), not a kiosk lockout. It runs on Windows only.
- Times are based on the city you set, so keep the city correct when you travel.
- The app must be running for alerts to fire — add it to startup (above) so it's
  always on.

---

## Already added

- ✅ **"I finished praying"** snooze button, gated to unlock 5 minutes into the lock.
- ✅ **Auto-location** by IP (first-run + Settings button).
- ✅ **Start-with-Windows** toggle in Settings.
- ✅ **Single shareable exe** with a one-click first-run setup.

## Extra feature suggestions

Ideas you could add next, roughly easiest → most involved:

1. **System tray icon** — minimize to the tray instead of the taskbar, with a
   right-click menu (Next prayer, Settings, Quit). Use `pystray` + `Pillow`.
2. **Adhan voice/muezzin picker** — bundle a few reciters and let the user choose
   per prayer (e.g., a softer one for Fajr).
3. **Qibla compass + Hijri date** — the Aladhan API already returns the Hijri
   date and can give the qibla direction for your coordinates.
7. **Weekly / monthly timetable view** — a table of upcoming days you can print.
8. **Offline mode** — cache a month of times (or compute locally) so it works
   without internet.
9. **Customizable lock behavior** — grace period before locking, "lock only for
   Fajr/Maghrib", or dim-screen-instead-of-lock options.
10. **Athkar / Quran reminders** — gentle post-prayer reminders, or a daily ayah.
11. **Multi-monitor overlay** — cover all displays, not just the primary one.
12. **Do-Not-Disturb awareness** — skip the lock during a calendar meeting.
13. **Code-signing the exe** — so Windows SmartScreen doesn't warn on first run.

---

*Built with Claude. Use and modify freely.*
