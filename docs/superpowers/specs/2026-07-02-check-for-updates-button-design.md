# Manual "Check for updates" button — Design

**Date:** 2026-07-02
**Target version:** 1.3.0 (bump from 1.2.0)

## Goal

Add a **"Check for updates"** button to the main window so users can check for a new
release on demand, instead of only getting the silent check that runs ~4 seconds after
launch. The button gives clear feedback in every outcome.

## Problem

`check_for_update()` (athan.py:182) currently returns a bare `(tag, url)` tuple on
success or `None` otherwise. `None` conflates four distinct situations:

- an update is available
- already on the latest version
- a network / GitHub error
- running as a dev script (`python athan.py`, not the frozen `.exe`) so self-update
  is impossible

A silent launch check only cares "is there an update," but a button must report each
of these to the user.

## Approach

Refactor `check_for_update()` to return a small status result. There is exactly one
existing caller (`_start_update_check`), so the refactor is clean.

Return an `UpdateCheck` result with a `status` field:

| status        | meaning                                          | carries        |
|---------------|--------------------------------------------------|----------------|
| `available`   | latest release tag is newer than `VERSION`       | `tag`, `url`   |
| `current`     | already on the latest version                    | —              |
| `error`       | network / GitHub / parse failure                 | short `message`|
| `unsupported` | dev run (not frozen) or `requests` missing       | —              |

Rejected alternatives:
- A separate parallel checker function for the button — duplicates the GitHub logic.
- Leaving the checker alone and inferring state in the button — impossible, `None`
  is ambiguous.

## Behavior

**Launch check** (`_start_update_check`): unchanged. Acts only on `available`; silent
for every other status.

**New button handler** (`_manual_update_check`):
1. Set status label to "Checking for updates…" and disable the button.
2. Run `check_for_update()` on a background daemon thread (keeps the Tk UI responsive).
3. Marshal the result back to the UI thread via `root.after(0, ...)`:
   - `available`   → existing `_prompt_update(tag, url)` dialog
   - `current`     → status: "You're on the latest version (v1.3.0)."
   - `error`       → status: "Couldn't check for updates — check your connection."
   - `unsupported` → status: "Update checks are only available in the installed app."
4. Re-enable the button in all cases.

## UI

Add a **"Check for updates"** button to the existing button row (athan.py:481),
alongside Settings / Refresh / Test athan, styled to match the existing buttons.

## Version / changelog

- Bump `VERSION` 1.2.0 → 1.3.0.
- Add a `CHANGELOG` entry at the top: manual "Check for updates" button with clear
  status feedback.

## Testing

- **Unit:** `check_for_update()` status classification becomes testable by mocking
  `requests` and `sys.frozen` — cover `available`, `current`, `error`, `unsupported`.
- **Manual:** build `dist\Athan.exe`, click the button, confirm the four outcomes'
  feedback (GUI + live network, not unit-testable).
