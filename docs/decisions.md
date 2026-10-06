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

## Phase 3 — Modes

**D-026 — Educational modes kept, not merged into guided drawing.**
They serve a different purpose: the colour and counting quizzes are *engagement and
proprioception* exercises with their own scoring, while guided drawing is an *assessment*. They
also still use finger combinations directly, which is exactly the skill they train. Merging them
would have produced one mode with two unrelated scoring models.

**D-027 — The free-draw palette moved from finger combinations to a dwell colour menu.**
Ten memorised combinations are a poor fit for a patient with limited dexterity, and every
transitional posture painted a stripe. Gestures now choose the *tool* (paint, erase, menu, pause)
and colour is chosen by dwelling on a swatch. The combination table survives in `palette.py`
because the colour quiz still teaches it.

**D-028 — Shapes defined in normalised coordinates, scored in normalised units.**
A score must be comparable between sessions even if the patient's laptop is plugged into a
different monitor. `test_scoring_is_resolution_independent` pins this down.

**D-029 — Difficulty changes both the corridor and the shape.**
Only narrowing the tolerance would make "hard" a test of camera noise. Harder levels also tilt
the line, shrink the circle, add zigzag peaks and add spiral turns, so the movement itself gets
harder, not just the measurement.

**D-030 — Score weights: 60% completion, 40% accuracy.**
Clinically, finishing the movement matters more than tracing it beautifully; a patient who
completes a rough circle has achieved more range than one who draws 20% of a perfect one. The
accuracy component reaches zero at twice the corridor width.

**D-031 — Dwell buttons go inert outside `IDLE` and `POINTING`.**
While painting, the pointer sweeps the whole screen and would otherwise trip "clear" or "quit"
on its way past. Their dwell timers are also reset, so crossing a button never leaves it
part-charged.

**D-032 — `BaseMode.observe()` runs the gesture engine and the recorder exactly once per frame.**
The previous design had each mode call `pointer()` and `read_states()` separately, which meant
the hysteresis estimator could be advanced twice in one frame. A single `FrameContext` makes
double-stepping impossible.

**D-033 — Metric recording is opt-in per mode (`records_metrics`).**
Only free draw, guided draw and physiotherapy feed the recorder; the menu and the quizzes do not,
so time spent navigating does not dilute the session's tracking-quality statistics.

**D-034 — The recorder stores derived features at 10 Hz, never frames.**
10 Hz is well above the bandwidth of voluntary hand movement (a fast tremor is 4-12 Hz, and the
Nyquist limit still holds at 10 Hz for the amplitude envelope we measure) while cutting stored
volume by two thirds versus 30 fps. Tracking quality is counted over *every* frame so the
presence ratio stays honest.

**D-035 — Each exercise run records a time window (`started_at`, `ended_at`).**
The metrics engine slices the shared session recording by window, so modes never need to know
anything about ROM, tremor or fatigue.

## Phase 4 — Metrics engine

**D-036 — The fingertip trajectory is recorded at the full frame rate, separately from the
10 Hz feature samples.**
Tremor lives at 4-12 Hz; by Nyquist a 10 Hz recording cannot resolve it at all. The trajectory
costs three floats per frame, so keeping it at 30 Hz is nearly free while the heavy feature
samples stay throttled. `test_a_ten_hertz_recording_cannot_resolve_the_band` pins the reasoning
into the test suite.

**D-037 — `band_measurable` is returned instead of a plausible wrong number.**
When the window is too short or the rate too low, the tremor ratio is reported as not
measurable rather than computed from aliased data. A clinical tool that silently returns
nonsense is worse than one that says it does not know.

**D-038 — Wrist measures are two explicit palm proxies, never a "wrist angle".**
MediaPipe has no forearm landmarks, so there is no anatomical reference for a wrist angle.
`palm_rotation` and `palm_openness` are named after what they actually measure, and
`WristEstimate.estimate` is `True` at the type level so no report can forget the label.

**D-039 — Fatigue compares thirds, using a symmetric bounded decline.**
First-versus-last repetition is too noisy; thirds average that out. `(start - end) /
max(start, end)` stays in `[-1, 1]` and remains defined when the patient started from no
measurable movement, which plain `(start - end) / start` does not.

**D-040 — The thumb is excluded from the fatigue amplitude.**
It is the noisiest of the five signals (D-016), so including it would mostly add variance.

**D-041 — Metrics are computed even for unreliable sessions; the report does the flagging.**
Returning `None` would force every consumer to special-case it. Instead `TrackingQuality`
travels with the numbers and carries a `warning_key` explaining exactly which threshold failed.

**D-042 — `TrackingQuality` lives in its own module, imported by the recorder.**
It is the gate on every other metric and is consumed by reports and the panel; burying it in
`recorder.py` would have made that dependency invisible.

**D-043 — NumPy is used for the tremor spectrum only.**
Everything else in `metrics/` is plain Python, so the modules stay importable and fast. NumPy is
already a transitive dependency of OpenCV, so this adds nothing to the install.
