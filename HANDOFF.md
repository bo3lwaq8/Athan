# Athan app — session handoff

## What this is
A Windows desktop prayer-times app (Python + Tkinter), shipped as `Athan.exe`
via PyInstaller. Built and working on the user's machine.

## Files (in C:\Users\alaso\Downloads\Athan-app)
- `athan.py` — the whole app (UI, scheduler, lock/overlay, location, autostart)
- `build.bat` — double-click on Windows → builds `dist\Athan.exe` (+ `Athan-Share.zip`)
- `config.json` — default settings (real settings get written next to the exe)
- `requirements.txt`, `README.md`
- `dist\Athan.exe` — already built (~16 MB), runs fine

## Key decisions made
- Prayer times from the **Aladhan API** (`timingsByCity`, or `timings` by lat/lon).
- Calculation method: **Umm al-Qura (Makkah)**, id 4 (user picked "the one in Mecca").
- At athan time: **both** a fullscreen overlay AND Windows `LockWorkStation()`.
- **15-min** warning popup before each prayer.
- **"I finished praying"** button on the overlay, gated to unlock only **5 min**
  after the lock starts.
- **Auto-location** by IP — switched to **HTTPS** provider `https://ipwho.is/`
  (was `http://ip-api.com`, fixed for the security review).
- **Start-with-Windows** toggle (writes HKCU `...\Run` registry key).
- Ships as a single exe; first run offers "auto-detect my location".
- A dhikr fade-in popup was added, then **reverted/removed** at user request.

## RESOLVED (2026-06-24) — location accuracy (was off ~4 min)
- Cause: IP geolocation pinned the user to **Salem** (ISP node) instead of
  Portland; the ~0.6deg latitude gap shifted times ~4 min.
- Added **Windows Location Services (GPS/WiFi)** via `winsdk` Geolocator:
  `detect_location_windows()`. `detect_location()` now tries GPS first, then
  falls back to IP (`detect_location_ip()`).
- Added **city search** (`geocode_city()`, Open-Meteo, no key) + a "search for
  your city" box in Settings with a results picker → sets exact coords.
- `requirements.txt`: added `winsdk` (win32 only).
- `build.bat`: now `--collect-all winsdk` (PyInstaller can't auto-find its lazy
  submodules) and pip-installs winsdk.
- **User must enable Windows Settings > Privacy > Location** for GPS; otherwise
  it silently falls back to IP — in that case use the city search box.
- **STILL TODO:** re-run `build.bat` on Windows to rebuild `dist\Athan.exe`.

## RESOLVED (2026-06-24) — high-latitude prayer times fixed
- Added Aladhan `latitudeAdjustmentMethod` to both calls in `fetch_prayer_times()`,
  wired to new config key `latitude_adjustment` (default **"Angle Based"** = 3).
- Default `method` changed from Umm al-Qura to **ISNA** (id 2) for North America;
  Umm al-Qura still selectable.
- New Settings dropdown: "High-latitude rule (for Fajr/Isha up north)".
- `config.json` defaults updated to match.
- Verified vs Aladhan API for Portland (45.52, -122.68) on 2026-06-24:
  Fajr 03:23, Dhuhr 13:13, Asr 17:24, Maghrib 21:04, Isha 23:03 — all sane
  (old output was Fajr 02:51 / Isha 22:33).
- **STILL TODO:** re-run `build.bat` on Windows to rebuild `dist\Athan.exe`
  (the shipped exe is still the old build). Test with `python athan.py` first.

## OLD OPEN ISSUE (now fixed above) — prayer times look "wrong"
User is in **Portland, OR** (app auto-detected nearby **Salem, OR** — same
latitude ~45.5°N, same timezone, so times are nearly identical).

**Diagnosis (verified by astronomical calc, NOT a timezone bug):**
- Dhuhr (13:15) and Maghrib (21:03) shown by the app are **correct** — computed
  solar noon ≈ 13:14 and sunset ≈ 21:04 for Portland on 2026-06-24 (PDT).
  So location + timezone are working fine.
- The real problem is **method + high latitude**. Umm al-Qura is calibrated for
  Makkah: Isha is a fixed **Maghrib + 90 min** (→ 22:33), and Fajr uses an 18.5°
  angle. At 45.5°N in **summer**, the sun barely/never reaches 18.5° below the
  horizon (persistent twilight), so Fajr/Isha come out off (app shows Fajr 02:51).

**Fix to implement next session:**
1. Add Aladhan's **`latitudeAdjustmentMethod`** parameter to both API calls in
   `fetch_prayer_times()` (1=Middle of Night, 2=One-Seventh, 3=Angle Based).
   Default to **3 (Angle Based)** — best for high latitudes like Portland.
2. Recommend/switch default method to **ISNA (id 2)** for North America (what
   local US mosques use), while keeping Umm al-Qura selectable.
3. Optionally expose the high-latitude rule as a Settings dropdown.
4. Rebuild via `build.bat` and re-test in Portland.

## Dhikr reminders — added 2026-07-01 (v1.1.0)
- After each prayer (default **8 min** after the prayer time, `dhikr_after_minutes`),
  a small popup shows **one random** post-salah dhikr from `DHIKR_REMINDERS`
  (Subhanallah 'adada khalqihi… / Astaghfirullah / La ilaha illa Allah wahdah…).
- Toggle: Settings → "Show dhikr reminder after each prayer" (`dhikr_reminders`).
- De-duped per prayer per day via `self.dhikr_shown`; cleared on day rollover
  and on settings save. Auto-closes after 90s.
- Note: earlier a *fade-in* dhikr popup was removed; this is the new, opt-out,
  post-prayer version the user asked for.

## Auto-update (GitHub Releases) — added 2026-07-01
- Repo: **https://github.com/bo3lwaq8/Athan** (public — release assets must be
  public so any user's app can download updates without credentials).
- The exe checks `releases/latest` on launch and, if the tag is newer than the
  `VERSION` constant in `athan.py`, offers to update (ask-first dialog), then
  downloads the new `Athan.exe` and swaps itself via a detached `athan_update.bat`
  (a running exe can't overwrite itself, so the helper waits for exit by PID,
  replaces the exe, and relaunches). Update code only runs in the frozen exe.
- **Release checklist when you change the code:**
  1. Bump `VERSION` in `athan.py` (e.g. `1.0.0` -> `1.0.1`).
  2. `build.bat` (or the PyInstaller onefile command) -> `dist\Athan.exe`.
  3. `gh release create v1.0.1 dist\Athan.exe --title "Athan v1.0.1" --notes "..."`
     (asset MUST be named exactly `Athan.exe`).
  4. Every installed copy auto-updates on its next launch. No more hand-sending.
- Future option: a GitHub Actions workflow could build the exe in the cloud on
  each tag, removing even the local build step.

## Build / run notes
- To test without building: `python athan.py` (dev runs skip the updater).
- Real settings persist in `config.json` next to the exe (in `dist\`), separate
  from the exe, so they survive rebuilds and updates.
- Claude is connected to the folder
  `C:\Users\alaso\OneDrive\Documents\Claude\Projects\Athan`.
