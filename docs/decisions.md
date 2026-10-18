# Architecture Decision Records (ADRs) — Aufgaben-Detector

This document records high-impact architectural choices, library selections, and design decisions to maintain technical consistency across development sessions and agent interactions.

---

## ADR-001: 2-Tier Modular Documentation & Session Memory Architecture

- **Date**: 2026-10-13
- **Status**: Accepted
- **Context**: Autonomous AI coding agents lose context across discrete sessions. Storing exhaustive documentation in a single prompt or root README leads to massive context bloat and token inefficiency.
- **Decision**: Adopt a strict 2-tier documentation hierarchy:
  1. `AGENTS.md` in the project root: Kept strictly under 3 KB (~500–800 tokens) as the master index loaded on every session start.
  2. `docs/`: Modular, on-demand markdown deep-dives (`project-overview.md`, `architecture.md`, `conventions.md`, `current-state.md`, `decisions.md`) retrieved via `view_file` only when required.
  3. `docs/current-state.md` serves as the persistent cross-session handoff log.
- **Consequences**:
  - Positive: Instant session bootstrap, zero token wastage, clear navigation pathways.
  - Negative: Agents must actively maintain and update `docs/current-state.md` upon completing work.

---

## ADR-002: Dual-Interface Architecture (Textual TUI & Headless Agent CLI)

- **Date**: 2026-10-06
- **Status**: Accepted
- **Context**: The tool is used by human students on their desktop PCs as well as by autonomous AI coding assistants and automation scripts. A GUI or interactive TUI is ideal for human students, but unusable or token-expensive for agents and terminal pipes.
- **Decision**: Implement a unified entry point (`main.py` / `tasks.bat`) that dynamically dispatches between:
  - **Headless Agent CLI (`src/core/agent_cli.py`)**: Activated whenever CLI arguments or subcommands are provided (`tasks list`, `tasks show 1`, `tasks sync`, etc.). Emits compact tables or pure JSON (`--json`).
  - **Textual TUI (`src/ui/tui_app.py`)**: Activated when invoked with zero arguments or `--tui`. Provides a mouse- and keyboard-interactive terminal application.
- **Consequences**:
  - Positive: Perfect experience for both human users and AI agents without duplicating data logic.
  - Negative: Requires maintaining both Textual widget states and CLI flag handlers.

---

## ADR-003: Playwright Persistent Browser Context for Microsoft Teams

- **Date**: 2026-10-04
- **Status**: Accepted
- **Context**: Microsoft Teams Education assignments cannot be queried via standard Graph API without tenant-wide administrator consent (which students cannot obtain). Students must also handle 2-Factor Authentication (2FA) and school SSO portals.
- **Decision**: Use Playwright with Chromium and a persistent user profile directory (`cache/teams_browser_profile/`). The user performs a one-time interactive login in a visible browser (`tasks -teams-login` or `[T]`), after which all background scrapers run in headless mode reusing session cookies and tokens.
- **Consequences**:
  - Positive: Completely bypasses Graph API permission hurdles; supports MFA/SSO seamlessly.
  - Negative: Requires Chromium browser installation (`playwright install chromium`), adding ~150 MB disk footprint.

---

## ADR-004: Direct WebUntis JSON-RPC with Timetable Lesson Matching

- **Date**: 2026-10-05
- **Status**: Accepted
- **Context**: WebUntis reports absence periods as raw calendar timestamps. However, students need to know the exact number of missed teaching units, accounting for free periods, room changes, cancelled classes (*Entfall*), and split workshop/laboratory groups (`1x` vs. `1y`).
- **Decision**: Directly communicate with the WebUntis JSON-RPC API (`getTimetable`, `getAbsences`, `getKlassen`). Map each absence period against the student's actual timetable for that day, filter group divisions according to `untis_group` in `config.json`, and count cancelled lessons appropriately.
- **Consequences**:
  - Positive: 100% accurate absence calculations matching the official school register.
  - Negative: Requires parsing both timetable lesson objects and absence intervals simultaneously.

---

## ADR-005: Local-First JSON Caching with Sub-100ms Read Performance

- **Date**: 2026-10-05
- **Status**: Accepted
- **Context**: Querying Moodle, Teams, and WebUntis over the network on every command execution introduces 2–10 seconds of latency, which ruins CLI and TUI responsiveness.
- **Decision**: Implement an offline-first caching layer (`cache/tasks_cache.json` and `cache/untis_cache.json`). All read operations load local JSON data synchronously (< 0.1s). Network operations are strictly decoupled and executed on explicit demand (`tasks sync` or `[R]`).
- **Consequences**:
  - Positive: Instant CLI output (`< 0.1s`), full offline capability, zero battery drain.
  - Negative: Cache may become stale until the next explicit or background sync.

---

## ADR-006: Hardware-ID Bound Licensing with HMAC-SHA256 for Distribution

- **Date**: 2026-10-07
- **Status**: Superseded by ADR-011
- **Context**: When sharing packaged installers (`setup_<Name>.exe`) with friends and classmates, individual configuration and access must be managed without sharing master credentials or allowing uncontrolled re-distribution.
- **Decision**: Implement hardware fingerprinting (`src/core/license.py`) using CPU ID, motherboard UUID, and MAC address. Generate activation keys via `installer/generate_license.py` using HMAC-SHA256 and an offline secret key (`license_secret.key`). Pre-built setups require valid activation upon first launch.
- **Consequences**:
  - Positive: Ensures distributed builds remain bound to authorized devices without cloud activation servers.
  - Negative: Hardware changes (e.g., motherboard replacement) require re-issuing an activation code.

---

## ADR-007: Reentrant Locking and Non-Interactive Subprocess Hardening for Git Cloud-Sync

- **Date**: 2026-10-13
- **Status**: Accepted
- **Context**: `GitSyncService` coordinates repository initialization, remote pulling, smart merging, and pushing across background threads and modal UI interactions. A standard non-reentrant mutex (`threading.Lock`) caused recursive self-deadlocks whenever `setup_repository()` called `pull_and_sync()` and `push_changes()`. Furthermore, unhandled git interactive prompts or GUI credential helpers could block background threads indefinitely under Windows.
- **Decision**:
  1. Use `threading.RLock()` for `_sync_lock` across all Git sync routines to safely permit recursive and reentrant service calls.
  2. Enforce strict headless execution in `_run_git_cmd()` by configuring `-c credential.helper=` and `-c core.askPass=` in conjunction with `GIT_TERMINAL_PROMPT=0`, `SSH_ASKPASS=""`, and `GCM_INTERACTIVE=never`.
  3. Wrap UI background threads (`GitSetupWorker`) in comprehensive exception guards to ensure interactive modals always receive completion signals and re-enable controls on failure.
  4. Skip redundant fetch calls on empty remotes and re-clone cleanly when the configured repository URL changes.
- **Consequences**:
  - Positive: Eliminates thread lockups, ensures sub-second failure reporting instead of indefinite hangs, and allows nested repository lifecycle operations safely.
  - Negative: Requires careful thread safety awareness when nested methods modify shared disk files.

---

## ADR-008: Dual-Mode CommandPalette with Dynamic Provider Isolation and Local-Only Schoolbook Storage

- **Date**: 2026-10-17
- **Status**: Accepted
- **Context**: Students need rapid access to local PDF textbooks and online school platforms (Trauner, Veritas, ÖBV) without navigating folder trees or browser bookmarks. The feature needs to be unified with the existing `Backspace` quick-jump modal while keeping absolute local filesystem paths strictly isolated per machine (avoiding broken links across multi-device Git synchronization).
- **Decision**:
  1. Subclass Textual's `CommandPalette` as `UnifiedCommandPalette` with a priority `Tab` keybinding to toggle between **Kurse** (displayed in turquoise `bold cyan`) and **Schulbücher** (displayed in `bold red`).
  2. Implement `UnifiedQuickOpenProvider` with dynamic mode binding via `UnifiedCommandPalette.current_mode`, strictly isolating course search hits from schoolbook hits so switching modes completely replaces list contents.
  3. Support `/` in Schulbücher mode to immediately list all management commands (`/link`, `/url`, `/unlink`) and existing books.
  4. Perform Windows Explorer PDF file picking thread-safely in background workers using Tkinter (`filedialog.askopenfilename`) with a PowerShell fallback.
  5. Store textbook metadata locally in `data/schoolbooks.json` and enforce complete Git isolation via `.gitignore`, `data/.gitignore`, and explicit exclusion from `GitSyncService.push_changes()`.
  6. Expose headless CLI commands `tasks books [list|open|add|remove]` for agentic workflows and scripts.
- **Consequences**:
  - Positive: Instant access (<0.05s) to schoolbooks without adding new global hotkeys; clean separation of machine-specific paths from cloud sync; thread-safe file dialogs without UI freezing.
  - Negative: Moving or deleting local PDF files outside the application requires updating or unlinking the stored entry.

---

## ADR-009: In-Palette Digi4School Book Grabber with OCR, TOC & Live Dynamic ETA

- **Date**: 2026-10-17
- **Status**: Accepted
- **Context**: Students access digital schoolbooks on Digi4School, but require searchable offline PDFs for study, offline reading, and note-taking. Digi4School enforces single-session constraints (Fehler 911), and publisher redirects route through external viewers (Hölzel-Pichler-Tempsky, Trauner, ÖBV). Users need to trigger downloads seamlessly from the search bar without persistent disk storage of credentials.
- **Decision**:
  1. Integrate `/download` (aliases `/d4s`, `/digi4school`) directly into the Schulbuch search palette, prefilling access codes when provided (e.g. `/download 26s7dbu5qxvw`).
  2. Prompt for Digi4School credentials and 12-digit code interactively on each download run via `Digi4SchoolDownloadModal` with immediate memory deletion after authentication (zero plain-text credential persistence on disk).
  3. Validate host system Tesseract OCR installation before initiating headless browser sessions; abort with an explicit `winget` installation guide if absent.
  4. Encapsulate download logic in `Digi4SchoolService` (`src/services/digi4school_service.py`), handling publisher redirects, LTI forms, automatic popup dismissal, parallel multi-core OCR (`ProcessPoolExecutor`), PDF bookmark outlines, in-page TOC hyperlinks, and page label synchronization.
  5. Provide `Digi4SchoolProgressModal` in the Textual TUI displaying live page & OCR progress, dynamic remaining time (ETA) calculations, and an error-911 warning banner.
  6. Automatically save output PDFs directly to `%USERPROFILE%\Downloads\` with a 1-click folder button in the completion screen.
  7. Expose headless CLI commands `tasks books download <code_or_index> [--email <m>] [--password <p>] [--json]` for automated scripts.
- **Consequences**:
  - Positive: Complete textbook grabber directly accessible in TUI and CLI without switching programs; produces 100% searchable OCR sandwich PDFs with interactive navigation; non-blocking UI with live ETA feedback.
  - Negative: Downloading full textbooks (300+ pages) requires moderate network bandwidth and intensive CPU utilization during parallel OCR processing.

---

## ADR-010: English-First UI & System Localization Architecture

- **Date**: 2026-10-17
- **Status**: Accepted
- **Context**: The codebase historically contained a mix of German and English UI labels, error strings, toasts, and CLI outputs. A clean, professional, and globally readable developer experience requires a consistent language across all program components, while respecting Austrian school requirements.
- **Decision**:
  1. **Standardized English**: All UI views, Textual modals, command palettes, buttons, table headers, toasts, CLI outputs/flags, logging, and error messages must be authored strictly in English. All future features and bug fixes must adhere to this standard.
  2. **Official Excuse Letter Exemption**: The generated excuse letter PDF (`src/services/excuse_service.py`) remains in Austrian German (*"Entschuldigung über das Fernbleiben vom Unterricht"*), as it is an official legal HTL school document. The surrounding modal UI (`ExcuseLetterModal`) remains in English.
  3. **Preservation of External School Data**: Incoming school data (course names, assignment titles, instructions from Moodle, Teams, or WebUntis) must be preserved in its original language and not machine-translated. Web scrapers must support dual-language DOM matchers for robust operation.
---

## ADR-011: Decommissioning Proprietary Licensing for Open-Source (MIT) & GitHub Release CI/CD

- **Date**: 2026-10-17
- **Status**: Accepted
- **Context**: The project was migrated from OneDrive to a public Git repository. Proprietary device-activation locks (HMAC-SHA256, hardware ID scanning, secret key embedding) are counterproductive in an open-source codebase. Releases should be distributed transparently via GitHub.
- **Decision**:
  1. Remove hardware-fingerprint scanning and activation gates completely (`src/core/license.py`, startup dialogs in `src/main.py`).
  2. Adopt the permissive **MIT License** for all source code.
  3. Standardize the Inno Setup installer builder (`installer/build_installer.py`) to produce universal installers (`AufgabenDetector_Setup.exe`) without needing recipient names or secret keys.
  4. Automatically download `python_installer.exe` on demand instead of checking 26 MB binaries into the Git repository.
  5. Establish an automated GitHub Actions workflow (`.github/workflows/release.yml`) to compile and attach installers to GitHub Releases on tag pushes (`v*`).
- **Consequences**:
  - Positive: Eliminates developer friction, enables open-source contribution, prevents binary bloat in Git, and automates multi-version installer releases.
  - Negative: None; access control is no longer required for an open-source community tool.

---

## ADR-012: Ultra-HD DeviceScaleFactor & Adaptive DPI Normalization for Digi4School Grabber

- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: Digital schoolbooks frequently contain fine vector graphics, mathematical symbols, and small typography. At standard resolution (scale 2.0), formulas appeared slightly blurry when zoomed in. Furthermore, users require flexibility to toggle OCR (e.g. for pure image archives), skip TOC extraction, customize quality presets, or manually adjust page numbering offsets.
- **Decision**:
  1. Set default Playwright `device_scale_factor` to **4.0** (Ultra-HD / Retina class) in `Digi4SchoolService`.
  2. Implement dynamic DPI coupling (`effective_dpi = dpi if dpi else int(150 * scale)`), yielding 600 DPI for Scale 4.0 and 300 DPI for Scale 2.0.
  3. Keep the physical PDF page size normalized to standard dimensions (A4/B5) by calculating `(median_px / effective_dpi) * 72.0` pt, so page size remains standard while embedded image sharpness is quadrupled.
  4. Expose CLI flags in `tasks books download`: `--scale` (float), `--quality` (standard, high, ultra), `--dpi` (int), `--no-ocr`, `--no-toc`, `--page-offset` (auto or int), `--visible`, and `--tesseract-cmd`.
  5. Add immediate in-memory password disposal (`del password`) right after filling authentication inputs for zero-knowledge safety.
- **Consequences**:
  - Positive: Crystal-clear 4K/Retina pages for reading on high-DPI tablets and monitors without PDF geometry distortion; versatile options for speed vs. quality.
  - Negative: Higher RAM and processing overhead during parallel OCR when rendering at Ultra-HD (Scale 4.0), which can be tuned down with `--quality standard` when needed.




