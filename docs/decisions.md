# Decision log

Decisions delegated to the implementation during the SPECTRA refactor.
Format: decision, then the reason. Written in English per the project language rule
(code, comments and technical docs in English; user-visible text in pt-BR).

## Phase 0 — Hygiene

**D-001 — Python 3.10 to 3.12, targeting 3.12.**
`mediapipe==0.10.21` publishes Windows wheels up to CPython 3.12 and none for 3.13.
3.12 is the common denominator between the author's Windows machine and the WSL dev box.

**D-002 — pytest configured in `pyproject.toml`, no `pytest.ini`.**
The brief asked for both, but `pytest.ini` takes precedence over `pyproject.toml`; having both
would hide the real configuration. A single source of truth (`[tool.pytest.ini_options]`) matches
the fixed decision to configure black/isort/ruff/pytest from `pyproject.toml`.

**D-003 — Coverage configured in `.coveragerc`.**
The fixed decision about `pyproject.toml` does not mention coverage, and the author's other
repositories use a standalone `.coveragerc`.

**D-004 — `hand_landmarker.task` stays tracked.**
The file is already in Git history, so removing it would not shrink the repository, and keeping it
lets the app run offline. `.gitignore` excludes every other `*.task` (copies downloaded into the
data directory) with an explicit exception for the root copy.

**D-005 — `requirements.txt` (runtime) split from `requirements-dev.txt` (lint/test).**
The headless test machine needs neither MediaPipe nor a webcam, so CI never installs the vision
stack.

**D-006 — Runtime dependencies pinned with `==`.**
Reproducibility is a thesis requirement: the examiner must be able to rebuild the environment.
`numpy` uses a range (`>=1.26,<2.2`) because it is a shared transitive dependency.

## Phase 1 — Package split

**D-007 — On-screen text is ASCII-folded in `spectra/ui/text.py`.**
OpenCV only ships Hershey vector fonts, which cannot render accents: `"Educação"` would come out
mangled. The catalog keeps correct pt-BR (needed for reports and the panel) and the drawing layer
strips diacritics at the last moment. Rejected alternative: embedding a TrueType font via Pillow,
which costs per-frame performance and adds a dependency to the patient app.

**D-008 — Detection returns `DetectionResult`/`DetectedHand` instead of two parallel lists.**
The original code passed `lm_list` and `hd_list` around and re-derived handedness in every mode.
An object with `for_label()` directly implements the fixed "one hand per session" decision.

**D-009 — MediaPipe is imported lazily, inside `HandDetector.__init__`.**
Every other module — and the whole test suite — can then be imported on Linux/WSL without the
vision stack installed.

**D-010 — `winsound` isolated behind `SoundPlayer` in `spectra/ui/sound.py`.**
Off Windows the import fails and every beep becomes a no-op, with no `try/except` scattered
through the code.

**D-011 — `AppMode` and `PhysioExercise` enum values are i18n keys.**
`AppMode.PHYSIO.value == "physio"` resolves `mode.physio` in the catalog, removing a parallel
enum-to-label map and guaranteeing that any new mode needs a translation.

**D-012 — `logging` instead of `print`; `ESC` as an emergency exit.**
The panel and the tests need to capture these messages. Patient interaction stays 100% gestural;
`ESC` exists only as a safety interrupt for the therapist.

**D-013 — "Guided draw" kept out of the menu until phase 3.**
Phase 1 is a pure code move, so the menu entry would be a dead button. The enum member
(`AppMode.GUIDED_DRAW`) already exists.

**D-014 — Outputs written to the data directory, never to the working directory.**
`pintura_*.png` goes to `<data_dir>/drawings` and the physiotherapy CSV to `<data_dir>/exports`.
This was the cause of the stray PNG in the repository root.

## Phase 2 — Gesture engine

**D-015 — Finger extension read from the mean of the two interphalangeal angles.**
A single angle (at PIP) is noisy when MediaPipe jitters one landmark; averaging PIP and DIP is
cheap and markedly more stable. Angles are invariant to rotation and scale, which the old
tip-versus-joint comparison was not. `tests/unit/test_features.py` keeps the old heuristic around
purely to demonstrate that it breaks on a tilted hand.

**D-016 — The thumb uses abduction, not an angle.**
A thumb's interphalangeal angle barely changes between an open hand and a fist (~173° vs ~143° on
synthetic hands, well inside the noise). Palm-normalised distance from the thumb tip to the index
MCP separates the two postures by roughly a factor of three.

**D-017 — All ratios normalised by palm size (wrist to middle MCP).**
Makes every threshold independent of how far the patient sits from the camera, so a single
calibration survives a change of chair.

**D-018 — Hysteresis thresholds derived as fractions of the patient's own open/closed range.**
`on = closed + 0.60 * range`, `off = closed + 0.40 * range`. The 20% dead band is wider than the
observed landmark jitter while still feeling responsive. A finger whose two postures are too
similar falls back to the defaults and is listed in `uncalibrated`, so the therapist is told
rather than silently given bad thresholds.

**D-019 — Temporal smoothing by majority vote over 3 frames, not an average.**
Finger states are boolean; a majority filter removes isolated dropouts without the half-open
states an average would produce, and 3 frames is ~100 ms at 30 fps, below the perception
threshold.

**D-020 — Hold time of 400 ms by default, 600 ms for the simplified profile.**
Inside the 300-500 ms band the brief allows. The simplified profile targets low dexterity, where
postures are reached more slowly, so it gets the longer window.

**D-021 — Pause is a toggle that must be re-armed.**
After a pause the gesture must be released before it can resume, otherwise holding a fist would
oscillate between paused and idle. Losing the hand never resumes a paused session: a patient who
drops out of frame must deliberately come back.

**D-022 — Overlapping triggers resolved by specificity, not declaration order.**
In the simplified profile "index only" and "pinch" can match the same frame; the pinch trigger is
more constrained and wins. Order-independence keeps serialised custom profiles deterministic.

**D-023 — The deliberate 1/2/3-finger ladder is exempt from the ambiguity warning.**
Those patterns differ by one finger *by design*. Warning about the shipped default would train the
therapist to ignore warnings. The exemption is an explicit allow-list (`PROGRESSIVE_PATTERNS`), so
any other one-finger-apart pair still warns.

**D-024 — A float tolerance (`HOLD_EPSILON`) on hold comparisons.**
Frame timestamps are floats; `0.76 - 0.36` is `0.3999999999999999`, which would silently drop an
exactly-held gesture. One microsecond of slack is far below any perceivable duration.

**D-025 — `SessionGuard` lives in `spectra/core`, not in `spectra/gestures`.**
The session time limit and rest prompts are not gesture concerns: the guided-draw and
physiotherapy modes need them too, and the reports will record them.
