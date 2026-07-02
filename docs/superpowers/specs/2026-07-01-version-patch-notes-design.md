# Version display + admin patch-notes page — design

Date: 2026-07-01
Status: Approved

## Goal
Show the app version to all users, and give the developer's own copy an
admin-only "Patch Notes" page listing what changed in each version.

## Requirements
1. **Version display (everyone)** — show the current `VERSION` as clean semver
   (e.g. `v1.1.0`) in the main window. No git/commit details.
2. **In-code changelog** — a `CHANGELOG` structure in `athan.py`, newest-first,
   editable each release.
3. **Admin detection** — the app is "admin" iff a file `admin.key` exists next to
   it (`app_dir()`). Public copies downloaded from GitHub never have it.
4. **Patch-notes page (admin only)** — a scrollable window listing every
   changelog entry (version + date header, changes as bullets). Reachable only
   in admin mode.

## Design

### Constants (top of athan.py, near VERSION)
- Keep `VERSION = "1.1.0"` (clean semver — the "main branch version").
- Add:
  ```python
  CHANGELOG = [
      ("1.1.0", "2026-07-01", [
          "Post-salah dhikr reminder (one random dhikr after each prayer).",
          "Auto-update via GitHub Releases (checks on launch).",
      ]),
      ("1.0.0", "2026-06-24", [
          "Initial release: prayer times with 15-min warning.",
          "Fullscreen overlay + Windows lock at athan time; 'I finished praying' gate.",
          "Auto-location (Windows GPS/WiFi + IP fallback) and city search.",
          "High-latitude Fajr/Isha rule; ISNA default calculation method.",
          "Start-with-Windows toggle.",
      ]),
  ]
  ```
- The top `CHANGELOG` version must always equal `VERSION`.

### `is_admin()` helper
- Returns `True` if `os.path.exists(os.path.join(app_dir(), "admin.key"))`.
- Presence is the only signal (no content check needed).

### UI changes (`_build_ui`)
- **Version label:** small grey label under the title, text `f"v{VERSION}"`.
- **Patch Notes button:** added to the existing button row ONLY when
  `is_admin()` is `True`. Hidden entirely for public copies.

### Patch-notes window (`open_patch_notes`)
- New `Toplevel`, dark theme to match the app.
- Scrollable (Canvas + inner Frame, or a read-only Text widget with a
  Scrollbar). For each `CHANGELOG` entry: a bold `vX.Y.Z · DATE` header and the
  changes as bullet lines, newest at top.

### Build / VCS hygiene
- Add `admin.key` to `.gitignore` so it never gets committed.
- Ensure `build.bat` / PyInstaller does not bundle `admin.key` (it is a loose
  file beside the exe, not an added-data asset — nothing to change unless it's
  explicitly added; verify it isn't).

## Out of scope (YAGNI)
- No git branch/commit info in the version string.
- No editing changelog from the UI (edited in code per release).
- No password, no separate admin build.

## Files touched
- `athan.py` — `CHANGELOG`, `is_admin()`, version label, conditional button,
  `open_patch_notes()`.
- `.gitignore` — add `admin.key`.
- `HANDOFF.md` — document the feature and the admin-key mechanism.
