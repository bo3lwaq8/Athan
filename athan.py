"""
Athan - Prayer Times Desktop App (Windows)
-------------------------------------------
- Simple Tkinter UI showing today's prayer times for your city.
- Fetches accurate times from the Aladhan API (Umm al-Qura / Makkah method).
- Notifies you 15 minutes before each prayer.
- When the athan time starts it shows a fullscreen overlay (plays athan
  audio if available) AND locks the Windows workstation.
- After praying you can press "I finished praying" to dismiss -- but the
  button only unlocks 5 minutes after the lockdown begins.
- Auto-detect location by IP, and a one-click "start with Windows" toggle.

Ships as a single standalone Athan.exe (see build.bat). The recipient just
runs it; on first launch it offers to auto-detect their city.

Run:        python athan.py
Build exe:  see build.bat  ->  produces dist/Athan.exe
"""

import os
import sys
import json
import time
import ctypes
import random
import datetime as dt
import threading
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import requests
except ImportError:
    requests = None

try:
    import winsound          # built into Windows Python; plays the athan WAV
except ImportError:
    winsound = None

try:
    import winreg            # for the "start with Windows" toggle (Windows only)
except ImportError:
    winreg = None

TIMINGS_BY_CITY = "https://api.aladhan.com/v1/timingsByCity"
TIMINGS_BY_COORDS = "https://api.aladhan.com/v1/timings"
IP_LOOKUP = "https://ipwho.is/"   # HTTPS, no API key needed (coarse fallback)
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"  # city name -> coords

# Aladhan calculation method IDs. 4 = Umm al-Qura University, Makkah.
METHODS = {
    "Umm al-Qura (Makkah)": 4,
    "Muslim World League": 3,
    "ISNA": 2,
    "Egyptian Authority": 5,
    "Karachi": 1,
}

# Aladhan high-latitude rules. Needed above ~48-49deg in summer, where the
# sun never dips far enough below the horizon for a true Fajr/Isha twilight.
# Angle Based (3) is the safest general default for high latitudes.
LAT_ADJUST = {
    "None": 0,
    "Middle of the Night": 1,
    "One Seventh of the Night": 2,
    "Angle Based": 3,
}

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

# Post-salah adhkar. A random one is shown a few minutes after each prayer.
DHIKR_REMINDERS = [
    "سبحان الله عدد خلقه ورضا نفسه وزنة عرشه ومداد كلماته",
    "أستغفر الله",
    "لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير",
]

APP_NAME = "Athan"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# ---- auto-update (GitHub Releases) ----
# Bump VERSION every time you cut a new release; the running app compares this
# to the latest release tag and offers to update itself. See build.bat / README.
VERSION = "1.1.0"
GITHUB_OWNER = "bo3lwaq8"
GITHUB_REPO = "Athan"
RELEASES_API = (f"https://api.github.com/repos/{GITHUB_OWNER}/"
                f"{GITHUB_REPO}/releases/latest")
UPDATE_ASSET = "Athan.exe"   # the release asset the updater downloads


def app_dir():
    """Folder where the script/exe lives (so config + audio sit next to it)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(app_dir(), "config.json")
AUDIO_PATH = os.path.join(app_dir(), "athan.wav")  # optional, place your own

DEFAULT_CONFIG = {
    "city": "Makkah",
    "country": "Saudi Arabia",
    "latitude": None,
    "longitude": None,
    "use_coordinates": False,
    "auto_location": True,
    "method": "ISNA",
    "latitude_adjustment": "Angle Based",
    "notify_minutes_before": 15,
    "snooze_minutes": 5,
    "lock_workstation": True,
    "show_overlay": True,
    "play_audio": True,
    "dhikr_reminders": True,      # show a post-salah dhikr after each prayer
    "dhikr_after_minutes": 8,     # how long after the prayer time to show it
    "first_run": True,
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("Could not save config:", e)


# ---------- auto-update ----------
def _parse_version(v):
    """'v1.2.3' -> (1, 2, 3); tolerant of junk so a bad tag never crashes us."""
    nums = []
    for part in (v or "").strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    return tuple(nums) or (0,)


def check_for_update():
    """Return (tag, download_url) if the latest GitHub release is newer than the
    running VERSION, else None. Only meaningful for the built exe; a dev run
    (python athan.py) can't swap itself, so we skip it. Never raises."""
    if requests is None or not getattr(sys, "frozen", False):
        return None
    try:
        r = requests.get(RELEASES_API, timeout=12,
                         headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        data = r.json()
        tag = data.get("tag_name", "")
        if _parse_version(tag) <= _parse_version(VERSION):
            return None
        for asset in data.get("assets", []):
            if asset.get("name") == UPDATE_ASSET:
                return tag, asset.get("browser_download_url")
    except Exception:
        return None
    return None


def download_and_apply_update(url):
    """Download the new exe next to the current one, then hand off to a small
    batch script that waits for THIS process to exit, replaces the exe, and
    relaunches it. Raises on download/write failure (caller shows the error).

    A running .exe is locked by Windows and cannot overwrite itself, hence the
    detached helper script that does the swap after we quit."""
    exe_path = sys.executable
    exe_dir = os.path.dirname(exe_path)
    new_path = os.path.join(exe_dir, "Athan_update.exe")
    bat_path = os.path.join(exe_dir, "athan_update.bat")

    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(new_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

    pid = os.getpid()
    bat = (
        "@echo off\r\n"
        ":wait\r\n"
        f'tasklist /fi "PID eq {pid}" 2>nul | find "{pid}" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "  timeout /t 1 /nobreak >nul\r\n"
        "  goto wait\r\n"
        ")\r\n"
        f'move /y "{new_path}" "{exe_path}" >nul\r\n'
        f'start "" "{exe_path}"\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat_path, "w", encoding="ascii") as f:
        f.write(bat)

    # Launch the helper detached and window-less so it outlives us and doesn't
    # flash a console, then the caller quits so the exe unlocks for the swap.
    import subprocess
    DETACHED_PROCESS = 0x00000008
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(["cmd", "/c", bat_path],
                     creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
                     close_fds=True)


# ---------- system helpers ----------
def lock_workstation():
    try:
        ctypes.windll.user32.LockWorkStation()
    except Exception as e:
        print("Lock failed (are you on Windows?):", e)


def stop_audio():
    if winsound is not None:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass


def play_athan_audio():
    if winsound is None:
        return
    if os.path.exists(AUDIO_PATH):
        try:
            winsound.PlaySound(AUDIO_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        except Exception:
            pass
    try:
        for _ in range(3):
            winsound.Beep(880, 250)
            winsound.Beep(660, 250)
    except Exception:
        pass


def run_command_for_autostart():
    """Command line Windows should run at login."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    return f'"{exe}" "{os.path.abspath(__file__)}"'


def is_autostart_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_autostart(enable):
    if winreg is None:
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                                  run_command_for_autostart())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
    except Exception as e:
        print("Autostart change failed:", e)


# ---------- location & times ----------
def detect_location_windows():
    """Return (lat, lon) from Windows Location Services (WiFi/GPS).
    Far more accurate than IP. Raises if unavailable, denied, or off-Windows."""
    try:
        from winsdk.windows.devices.geolocation import Geolocator, PositionAccuracy
    except Exception:
        try:
            from winrt.windows.devices.geolocation import Geolocator, PositionAccuracy
        except Exception as e:
            raise RuntimeError("Windows Location API not available") from e
    import asyncio

    async def _get():
        loc = Geolocator()
        try:
            loc.desired_accuracy = PositionAccuracy.HIGH
        except Exception:
            pass
        pos = await loc.get_geoposition_async()
        p = pos.coordinate.point.position
        return p.latitude, p.longitude

    return asyncio.run(_get())


def detect_location_ip():
    """Return (city, country, lat, lon) from the device IP, or raise.
    Coarse: locates the ISP node (often a neighbouring city), not the device."""
    if requests is None:
        raise RuntimeError("The 'requests' package is not installed.")
    r = requests.get(IP_LOOKUP, timeout=12)
    r.raise_for_status()
    d = r.json()
    if not d.get("success", False):
        raise RuntimeError("IP location lookup failed.")
    return d.get("city"), d.get("country"), d.get("latitude"), d.get("longitude")


def detect_location():
    """Best-effort auto-location. Tries precise Windows GPS/WiFi first, then
    falls back to coarse IP geolocation. Returns (city, country, lat, lon)."""
    try:
        lat, lon = detect_location_windows()
        if lat is not None:
            return "My location", None, lat, lon
    except Exception:
        pass
    return detect_location_ip()


def geocode_city(query):
    """Look a place up by name (Open-Meteo, no key). Returns a list of match
    dicts {label, city, country, latitude, longitude}; [] if nothing found."""
    if requests is None:
        raise RuntimeError("The 'requests' package is not installed.")
    r = requests.get(GEOCODE_URL,
                     params={"name": query, "count": 5,
                             "language": "en", "format": "json"},
                     timeout=12)
    r.raise_for_status()
    out = []
    for m in (r.json().get("results") or []):
        parts = [p for p in (m.get("name"), m.get("admin1"), m.get("country")) if p]
        out.append({"label": ", ".join(parts),
                    "city": m.get("name"), "country": m.get("country"),
                    "latitude": m.get("latitude"), "longitude": m.get("longitude")})
    return out


def fetch_prayer_times(cfg):
    """Return dict {prayer: 'HH:MM'} for today, or raise on failure."""
    if requests is None:
        raise RuntimeError("The 'requests' package is not installed.")
    method_id = METHODS.get(cfg.get("method"), 2)
    lat_adj = LAT_ADJUST.get(cfg.get("latitude_adjustment"), 3)

    if cfg.get("use_coordinates") and cfg.get("latitude") is not None:
        params = {"latitude": cfg["latitude"], "longitude": cfg["longitude"],
                  "method": method_id, "school": 0,
                  "latitudeAdjustmentMethod": lat_adj}
        r = requests.get(TIMINGS_BY_COORDS, params=params, timeout=15)
    else:
        params = {"city": cfg["city"], "country": cfg["country"],
                  "method": method_id, "school": 0,
                  "latitudeAdjustmentMethod": lat_adj}
        r = requests.get(TIMINGS_BY_CITY, params=params, timeout=15)

    r.raise_for_status()
    timings = r.json()["data"]["timings"]
    return {p: timings[p].split(" ")[0] for p in PRAYERS}   # "05:14 (+03)" -> "05:14"


class AthanApp:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.times = {}
        self.notified = set()
        self.fired = set()
        self.dhikr_shown = set()
        self.today = dt.date.today()
        self._stop = False
        self.overlay = None

        root.title("Athan - Prayer Times")
        root.geometry("420x600")
        root.minsize(380, 560)
        root.configure(bg="#0d1b2a")

        self._build_ui()

        # First-run welcome (offer auto-detect) before anything else.
        if self.cfg.get("first_run", False):
            self.root.after(300, self.first_run_setup)
        else:
            self.refresh_times(initial=True)

        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        # A few seconds after launch, quietly check GitHub for a newer release.
        self.root.after(4000, self._start_update_check)

    # ---------- UI ----------
    def _build_ui(self):
        bg, fg, accent = "#0d1b2a", "#e0e1dd", "#e9c46a"

        tk.Label(self.root, text="☪  Athan", font=("Segoe UI", 26, "bold"),
                 bg=bg, fg=accent).pack(pady=(18, 2))

        self.loc_label = tk.Label(self.root, text="", font=("Segoe UI", 11), bg=bg, fg=fg)
        self.loc_label.pack()

        self.clock_label = tk.Label(self.root, text="", font=("Consolas", 22, "bold"),
                                    bg=bg, fg="#90e0ef")
        self.clock_label.pack(pady=(6, 4))

        self.next_label = tk.Label(self.root, text="", font=("Segoe UI", 11, "italic"),
                                   bg=bg, fg=accent)
        self.next_label.pack(pady=(0, 10))

        self.rows = {}
        card = tk.Frame(self.root, bg="#1b263b")
        card.pack(padx=18, fill="x")
        for p in PRAYERS:
            row = tk.Frame(card, bg="#1b263b")
            row.pack(fill="x", padx=14, pady=6)
            tk.Label(row, text=p, font=("Segoe UI", 13, "bold"), bg="#1b263b",
                     fg=fg, width=10, anchor="w").pack(side="left")
            val = tk.Label(row, text="--:--", font=("Consolas", 14),
                           bg="#1b263b", fg="#90e0ef")
            val.pack(side="right")
            self.rows[p] = val

        btns = tk.Frame(self.root, bg=bg)
        btns.pack(pady=14)
        tk.Button(btns, text="Settings", command=self.open_settings, bg=accent,
                  fg="#0d1b2a", font=("Segoe UI", 10, "bold"), relief="flat",
                  padx=14, pady=6).pack(side="left", padx=6)
        tk.Button(btns, text="Refresh", command=lambda: self.refresh_times(),
                  bg="#90e0ef", fg="#0d1b2a", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=6).pack(side="left", padx=6)
        tk.Button(btns, text="Test athan", command=lambda: self.trigger_athan(),
                  bg="#577590", fg="#e0e1dd", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=6).pack(side="left", padx=6)

        self.status = tk.Label(self.root, text="", font=("Segoe UI", 9),
                               bg=bg, fg="#778da9")
        self.status.pack(side="bottom", pady=8)

        self._tick_clock()

    def _tick_clock(self):
        now = dt.datetime.now()
        self.clock_label.config(text=now.strftime("%H:%M:%S"))
        self._update_next_label(now)
        if now.date() != self.today:
            self.today = now.date()
            self.notified.clear()
            self.fired.clear()
            self.dhikr_shown.clear()
            self.refresh_times()
        self.root.after(1000, self._tick_clock)

    def _update_next_label(self, now):
        nxt = self._next_prayer(now)
        if not nxt:
            self.next_label.config(text="")
            return
        name, when = nxt
        mins = int((when - now).total_seconds() // 60)
        h, m = divmod(mins, 60)
        eta = f"{h}h {m}m" if h else f"{m}m"
        self.next_label.config(text=f"Next: {name} in {eta}")

    def _next_prayer(self, now):
        upcoming = []
        for p in PRAYERS:
            t = self.times.get(p)
            if t:
                when = self._today_at(t, now)
                if when > now:
                    upcoming.append((p, when))
        return min(upcoming, key=lambda x: x[1]) if upcoming else None

    @staticmethod
    def _today_at(hhmm, now):
        hh, mm = map(int, hhmm.split(":"))
        return now.replace(hour=hh, minute=mm, second=0, microsecond=0)

    # ---------- first run ----------
    def first_run_setup(self):
        win = tk.Toplevel(self.root)
        win.title("Welcome to Athan")
        win.configure(bg="#0d1b2a")
        win.geometry("360x230")
        win.attributes("-topmost", True)
        win.grab_set()

        tk.Label(win, text="☪  Welcome", font=("Segoe UI", 18, "bold"),
                 bg="#0d1b2a", fg="#e9c46a").pack(pady=(18, 6))
        tk.Label(win, text="Let's set your location for accurate\nprayer times.",
                 font=("Segoe UI", 11), bg="#0d1b2a", fg="#e0e1dd").pack()

        status = tk.Label(win, text="", font=("Segoe UI", 9),
                          bg="#0d1b2a", fg="#90e0ef")
        status.pack(pady=6)

        def auto():
            status.config(text="Detecting your location…")
            win.update_idletasks()

            def work():
                try:
                    city, country, lat, lon = detect_location()
                    self.cfg.update({"city": city or self.cfg["city"],
                                     "country": country or self.cfg["country"],
                                     "latitude": lat, "longitude": lon,
                                     "use_coordinates": lat is not None,
                                     "auto_location": True})
                    self.root.after(0, done)
                except Exception as e:
                    self.root.after(0, lambda: status.config(text=f"Auto-detect failed: {e}"))
            threading.Thread(target=work, daemon=True).start()

        def done():
            self.cfg["first_run"] = False
            save_config(self.cfg)
            win.destroy()
            self.refresh_times()

        def manual():
            self.cfg["first_run"] = False
            save_config(self.cfg)
            win.destroy()
            self.open_settings()

        tk.Button(win, text="📍  Auto-detect my location", command=auto,
                  bg="#e9c46a", fg="#0d1b2a", font=("Segoe UI", 11, "bold"),
                  relief="flat", padx=16, pady=8).pack(pady=(10, 4))
        tk.Button(win, text="Enter city manually", command=manual,
                  bg="#577590", fg="#e0e1dd", font=("Segoe UI", 10),
                  relief="flat", padx=12, pady=6).pack()

    # ---------- data ----------
    def refresh_times(self, initial=False):
        loc = (f"{self.cfg['city']}, {self.cfg['country']}"
               if not self.cfg.get("use_coordinates")
               else f"{self.cfg['city'] or 'My location'} (GPS)")
        self.loc_label.config(text=f"{loc}  ·  {self.cfg['method']}")
        self.status.config(text="Fetching prayer times…")

        def work():
            try:
                times = fetch_prayer_times(self.cfg)
                self.times = times
                self.root.after(0, self._apply_times)
            except Exception as e:
                self.root.after(0, lambda: self.status.config(text=f"Could not fetch times: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def _apply_times(self):
        for p in PRAYERS:
            self.rows[p].config(text=self.times.get(p, "--:--"))
        self.status.config(text=f"Updated {dt.datetime.now():%H:%M:%S}")

    # ---------- scheduler ----------
    def _scheduler_loop(self):
        while not self._stop:
            try:
                self._check_schedule()
            except Exception as e:
                print("scheduler error:", e)
            time.sleep(20)

    def _check_schedule(self):
        if not self.times:
            return
        now = dt.datetime.now()
        before = int(self.cfg.get("notify_minutes_before", 15))
        dhikr_after = int(self.cfg.get("dhikr_after_minutes", 8))
        for p in PRAYERS:
            t = self.times.get(p)
            if not t:
                continue
            when = self._today_at(t, now)
            notify_at = when - dt.timedelta(minutes=before)
            nkey, fkey = f"{self.today}-{p}-notify", f"{self.today}-{p}-fire"
            dkey = f"{self.today}-{p}-dhikr"

            if nkey not in self.notified and notify_at <= now < notify_at + dt.timedelta(seconds=90):
                self.notified.add(nkey)
                self.root.after(0, lambda pp=p, bb=before: self.show_notification(pp, bb))

            if fkey not in self.fired and when <= now < when + dt.timedelta(seconds=90):
                self.fired.add(fkey)
                self.root.after(0, lambda pp=p: self.trigger_athan(pp))

            # A few minutes after the prayer time, show a random post-salah dhikr.
            dhikr_at = when + dt.timedelta(minutes=dhikr_after)
            if (self.cfg.get("dhikr_reminders", True) and dkey not in self.dhikr_shown
                    and dhikr_at <= now < dhikr_at + dt.timedelta(seconds=90)):
                self.dhikr_shown.add(dkey)
                self.root.after(0, self.show_dhikr_reminder)

    # ---------- actions ----------
    def show_notification(self, prayer, minutes):
        top = tk.Toplevel(self.root)
        top.title("Athan reminder")
        top.configure(bg="#1b263b")
        top.attributes("-topmost", True)
        top.geometry("320x150")
        tk.Label(top, text="⏰  Reminder", font=("Segoe UI", 14, "bold"),
                 bg="#1b263b", fg="#e9c46a").pack(pady=(16, 4))
        tk.Label(top, text=f"{prayer} is in {minutes} minutes\n({self.times.get(prayer,'')})",
                 font=("Segoe UI", 12), bg="#1b263b", fg="#e0e1dd").pack()
        tk.Button(top, text="OK", command=top.destroy, bg="#e9c46a", fg="#0d1b2a",
                  relief="flat", padx=20, pady=4).pack(pady=12)
        top.after(60000, top.destroy)

    def show_dhikr_reminder(self):
        """A gentle post-salah reminder showing one random dhikr."""
        if not self.cfg.get("dhikr_reminders", True):
            return
        phrase = random.choice(DHIKR_REMINDERS)
        top = tk.Toplevel(self.root)
        top.title("Dhikr")
        top.configure(bg="#1b263b")
        top.attributes("-topmost", True)
        top.geometry("480x240")
        tk.Label(top, text="📿  ذِكر", font=("Segoe UI", 16, "bold"),
                 bg="#1b263b", fg="#e9c46a").pack(pady=(20, 10))
        tk.Label(top, text=phrase, font=("Segoe UI", 17), bg="#1b263b",
                 fg="#e0e1dd", wraplength=430, justify="center").pack(padx=24, pady=8)
        tk.Button(top, text="آمين", command=top.destroy, bg="#e9c46a", fg="#0d1b2a",
                  font=("Segoe UI", 11, "bold"), relief="flat",
                  padx=28, pady=6).pack(pady=16)
        top.after(90000, top.destroy)   # auto-close after 90s if ignored

    def trigger_athan(self, prayer="Test"):
        if self.cfg.get("play_audio", True):
            threading.Thread(target=play_athan_audio, daemon=True).start()
        if self.cfg.get("show_overlay", True):
            self.show_overlay(prayer)
        else:
            self._do_lock()

    def show_overlay(self, prayer):
        if self.overlay is not None:
            return
        ov = tk.Toplevel(self.root)
        self.overlay = ov
        ov.configure(bg="#000000")
        ov.attributes("-fullscreen", True)
        ov.attributes("-topmost", True)

        tk.Label(ov, text="☪", font=("Segoe UI", 90), bg="#000000",
                 fg="#e9c46a").pack(pady=(110, 10))
        tk.Label(ov, text="Allahu Akbar", font=("Segoe UI", 40, "bold"),
                 bg="#000000", fg="#e0e1dd").pack()
        tk.Label(ov, text=f"It is time for {prayer}", font=("Segoe UI", 22),
                 bg="#000000", fg="#90e0ef").pack(pady=10)

        info = tk.Label(ov, text="The screen will lock for prayer.",
                        font=("Segoe UI", 13), bg="#000000", fg="#778da9")
        info.pack(pady=8)

        snooze_secs = int(self.cfg.get("snooze_minutes", 5)) * 60
        btn = tk.Button(ov, text="I finished praying", state="disabled",
                        bg="#3a3a3a", fg="#888888", font=("Segoe UI", 13, "bold"),
                        relief="flat", padx=24, pady=10)
        btn.pack(pady=26)

        def finish():
            stop_audio()
            ov.destroy()
            self.overlay = None

        btn.config(command=finish)

        def countdown():
            if self.overlay is None:
                return
            elapsed = time.time() - self.lock_started
            remaining = int(snooze_secs - elapsed)
            if remaining > 0:
                m, s = divmod(remaining, 60)
                info.config(text=f"You can mark prayer finished in {m}:{s:02d}")
                btn.config(state="disabled", bg="#3a3a3a", fg="#888888")
                ov.after(1000, countdown)
            else:
                info.config(text="Done praying? You can close this now.")
                btn.config(state="normal", text="✓  I finished praying",
                           bg="#e9c46a", fg="#000000")

        def lock_and_start():
            self._do_lock()
            self.lock_started = time.time()
            countdown()

        # Give a few seconds to read / hear the athan before locking.
        ov.after(4000, lock_and_start)

    def _do_lock(self):
        if self.cfg.get("lock_workstation", True):
            lock_workstation()

    # ---------- settings ----------
    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.configure(bg="#0d1b2a")
        win.geometry("360x640")
        win.attributes("-topmost", True)

        pad = {"padx": 16, "pady": 4}
        fg = "#0d1b2a"

        def label(txt):
            tk.Label(win, text=txt, bg="#0d1b2a", fg="#e0e1dd",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", **pad)

        city_var = tk.StringVar(value=self.cfg["city"])
        country_var = tk.StringVar(value=self.cfg["country"])

        label("City")
        tk.Entry(win, textvariable=city_var).pack(fill="x", padx=16)
        label("Country")
        tk.Entry(win, textvariable=country_var).pack(fill="x", padx=16)

        loc_status = tk.Label(win, text="", bg="#0d1b2a", fg="#90e0ef",
                              font=("Segoe UI", 9))

        def auto_detect():
            loc_status.config(text="Detecting…")
            win.update_idletasks()

            def work():
                try:
                    city, country, lat, lon = detect_location()
                    self.cfg.update({"latitude": lat, "longitude": lon,
                                     "use_coordinates": lat is not None})
                    found = ", ".join(p for p in (city, country) if p) or "location"
                    self.root.after(0, lambda: (city_var.set(city or ""),
                                                country_var.set(country or ""),
                                                loc_status.config(
                                                    text=f"Found: {found} "
                                                         f"({lat:.3f}, {lon:.3f})")))
                except Exception as e:
                    self.root.after(0, lambda: loc_status.config(text=f"Failed: {e}"))
            threading.Thread(target=work, daemon=True).start()

        tk.Button(win, text="📍 Auto-detect location", command=auto_detect,
                  bg="#90e0ef", fg="#0d1b2a", font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4).pack(pady=(8, 0))
        loc_status.pack()

        label("Or search for your city (most accurate)")
        search_frame = tk.Frame(win, bg="#0d1b2a")
        search_frame.pack(fill="x", padx=16)
        search_var = tk.StringVar()
        tk.Entry(search_frame, textvariable=search_var).pack(
            side="left", fill="x", expand=True)
        matches_box = ttk.Combobox(win, state="readonly", values=[])
        geo_results = {}

        def pick_match(*_):
            m = geo_results.get(matches_box.get())
            if not m:
                return
            city_var.set(m["city"] or "")
            country_var.set(m["country"] or "")
            self.cfg.update({"latitude": m["latitude"],
                             "longitude": m["longitude"],
                             "use_coordinates": True})
            loc_status.config(text=f"Set: {m['label']}")

        def do_search():
            q = search_var.get().strip()
            if not q:
                return
            loc_status.config(text="Searching…")

            def work():
                try:
                    res = geocode_city(q)
                    geo_results.clear()
                    labels = []
                    for m in res:
                        geo_results[m["label"]] = m
                        labels.append(m["label"])

                    def upd():
                        matches_box["values"] = labels
                        if labels:
                            matches_box.set(labels[0])
                            pick_match()
                            loc_status.config(
                                text=f"{len(labels)} match(es) — pick one if wrong")
                        else:
                            loc_status.config(text="No matches found")
                    self.root.after(0, upd)
                except Exception as e:
                    self.root.after(0, lambda: loc_status.config(
                        text=f"Search failed: {e}"))
            threading.Thread(target=work, daemon=True).start()

        matches_box.bind("<<ComboboxSelected>>", pick_match)
        tk.Button(search_frame, text="Search", command=do_search,
                  bg="#90e0ef", fg="#0d1b2a", font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10).pack(side="left", padx=(6, 0))
        matches_box.pack(fill="x", padx=16, pady=(4, 0))

        label("Calculation method")
        method_var = tk.StringVar(value=self.cfg["method"])
        ttk.Combobox(win, textvariable=method_var, values=list(METHODS.keys()),
                     state="readonly").pack(fill="x", padx=16)

        label("High-latitude rule (for Fajr/Isha up north)")
        lat_adj_var = tk.StringVar(
            value=self.cfg.get("latitude_adjustment", "Angle Based"))
        ttk.Combobox(win, textvariable=lat_adj_var, values=list(LAT_ADJUST.keys()),
                     state="readonly").pack(fill="x", padx=16)

        label("Notify minutes before athan")
        notify_var = tk.IntVar(value=int(self.cfg["notify_minutes_before"]))
        tk.Spinbox(win, from_=1, to=60, textvariable=notify_var).pack(fill="x", padx=16)

        label("Minutes locked before 'finished' unlocks")
        snooze_var = tk.IntVar(value=int(self.cfg.get("snooze_minutes", 5)))
        tk.Spinbox(win, from_=1, to=30, textvariable=snooze_var).pack(fill="x", padx=16)

        lock_var = tk.BooleanVar(value=self.cfg["lock_workstation"])
        overlay_var = tk.BooleanVar(value=self.cfg["show_overlay"])
        audio_var = tk.BooleanVar(value=self.cfg["play_audio"])
        dhikr_var = tk.BooleanVar(value=self.cfg.get("dhikr_reminders", True))
        auto_loc_var = tk.BooleanVar(value=self.cfg.get("use_coordinates", False))
        autostart_var = tk.BooleanVar(value=is_autostart_enabled())

        def chk(text, var):
            tk.Checkbutton(win, text=text, variable=var, bg="#0d1b2a", fg="#e0e1dd",
                           selectcolor="#1b263b", activebackground="#0d1b2a",
                           font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=2)

        chk("Lock workstation at athan", lock_var)
        chk("Show fullscreen overlay", overlay_var)
        chk("Play athan audio", audio_var)
        chk("Show dhikr reminder after each prayer", dhikr_var)
        chk("Use auto-detected GPS coordinates", auto_loc_var)
        chk("Start Athan when Windows starts", autostart_var)

        def save():
            self.cfg.update({
                "city": city_var.get().strip() or "Makkah",
                "country": country_var.get().strip() or "Saudi Arabia",
                "method": method_var.get(),
                "latitude_adjustment": lat_adj_var.get(),
                "notify_minutes_before": int(notify_var.get()),
                "snooze_minutes": int(snooze_var.get()),
                "lock_workstation": lock_var.get(),
                "show_overlay": overlay_var.get(),
                "play_audio": audio_var.get(),
                "dhikr_reminders": dhikr_var.get(),
                "use_coordinates": auto_loc_var.get(),
                "first_run": False,
            })
            set_autostart(autostart_var.get())
            save_config(self.cfg)
            self.notified.clear()
            self.fired.clear()
            self.dhikr_shown.clear()
            win.destroy()
            self.refresh_times()

        tk.Button(win, text="Save", command=save, bg="#e9c46a", fg="#0d1b2a",
                  font=("Segoe UI", 11, "bold"), relief="flat",
                  padx=24, pady=8).pack(pady=18)

    # ---------- auto-update ----------
    def _start_update_check(self):
        def work():
            info = check_for_update()
            if info:
                tag, url = info
                self.root.after(0, lambda: self._prompt_update(tag, url))
        threading.Thread(target=work, daemon=True).start()

    def _prompt_update(self, tag, url):
        if not messagebox.askyesno(
                "Update available",
                f"A new version of Athan ({tag}) is available.\n"
                f"You have v{VERSION}.\n\n"
                "Update now? Athan will briefly close and reopen."):
            return
        self.status.config(text="Downloading update…")

        def work():
            try:
                download_and_apply_update(url)
                self.root.after(0, self._quit_for_update)
            except Exception as e:
                self.root.after(0, lambda: self.status.config(
                    text=f"Update failed: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def _quit_for_update(self):
        # Leave without the "you'll miss alerts" prompt; the helper relaunches us.
        self._stop = True
        self.root.destroy()

    def on_close(self):
        if messagebox.askokcancel("Quit", "Stop Athan? You will not get prayer alerts."):
            self._stop = True
            self.root.destroy()


def main():
    if requests is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Missing dependency",
                             "The 'requests' package is required.\n\nRun: pip install requests")
        return
    root = tk.Tk()
    AthanApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
