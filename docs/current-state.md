# Current Project State & Session Handoff — Aufgaben-Detector

> **Last Updated**: 2026-10-19  
> **Active Milestone**: Milestone 3 — Open Source Release & GitHub Actions CI/CD (v1.0.3)

---

## 1. Completed Tasks & Milestones

- [x] **Documentation Modernization**:
  - Replaced legacy documentation files with standardized 2-tier persistent memory structure.
  - Created lean `< 3 KB` `AGENTS.md` master index for instant Antigravity session bootstrap.
  - Modularized domain documentation into `docs/project-overview.md`, `architecture.md`, `conventions.md`, `current-state.md`, and `decisions.md`.
- [x] **Multi-Platform Task Aggregation**:
  - Consolidated Moodle (`mod_assign`, calendar) and Microsoft Teams Education assignments into unified `Task` models.
  - Implemented persistent caching (`cache/tasks_cache.json`) enabling `< 0.1s` instant offline startup.
  - Added multi-level filtering (platform, subject, completion status, overdue).
- [x] **Interactive Textual TUI**:
  - Full keyboard & mouse-driven terminal application with color themes (Nord, Catppuccin, Monokai, Dracula).
  - Quick-Jump fuzzy course opener (`Backspace`), task detail viewer, and manual task creation modal.
- [x] **WebUntis Timetable & Absence Accounting**:
  - Correlated raw absence intervals with daily lesson timetables to calculate actual missed periods.
  - Filtered split workshop/lab classes (`1x` vs `1y`) and handled cancelled periods (*Entfall*).
  - Integrated exam planner (`UntisExam`) with custom revision notes.
- [x] **Headless Agent CLI (`tasks`)**:
  - Implemented token-efficient CLI dispatcher in `src/core/agent_cli.py`.
  - Supported subcommands and flags (`list`, `show`, `download`, `open`, `courses`, `add`, `done`, `delete`, `restore`, `sync`, `guide`).
  - Added `--json` output option for programmatic consumption by AI agents and scripts.
- [x] **Download & Document Generation**:
  - 1-Click download of assignment attachments and markdown problem statement (`angabe.md`) to `%USERPROFILE%\Downloads\<Fach> - <Titel>\`.
  - Automated PDF absence excuse generator using ReportLab / fpdf2 with official school header.
- [x] **Open-Source Distribution & Automated Releases**:
  - Transitioned from proprietary device-licensing to standard open-source **MIT License** (`LICENSE`).
  - Completely removed hardware-fingerprinting, secret keys, and activation prompts.
  - Refactored Inno Setup 6 packaging pipeline (`installer/build_installer.py` & `installer/aufgaben_detector.iss`) to produce universal `AufgabenDetector_Setup.exe` with on-demand Python 3.12 download.
  - Created automated GitHub Actions CI/CD workflow (`.github/workflows/release.yml`) building and publishing release installers upon Git tag pushes (`v*`).
  - Successfully published official release **[v1.0.0](https://github.com/X4nd109/Aufgaben-Detector/releases/tag/v1.0.0)** with bundled `AufgabenDetector_Setup.exe`.

- [x] **Git Cloud-Sync Deadlock & Connection Fix**:
  - Replaced non-reentrant `threading.Lock` with `threading.RLock` in [`git_sync_service.py`](../src/services/git_sync_service.py), eliminating mutual self-deadlock between `setup_repository`, `pull_and_sync`, and `push_changes`.
  - Added `-c core.askPass=` and `SSH_ASKPASS` to `_run_git_cmd` to strictly prevent external GUI/credential prompts from blocking background execution.
  - Hardened TUI `GitSetupModal` background worker with robust error recovery so UI status and connect buttons never freeze.
  - Handled clean repo-switching and empty remote branches without redundant failed fetch calls.

- [x] **Schulbuch-Schnellzugriff (Schoolbooks Quick-Open)**:
  - Unified `Backspace` CommandPalette switching between **Kurse** (Türkis/Cyan) and **Schulbücher** (Rot) via `Tabulator`.
  - Local PDF linking via `/link` opening native Windows Explorer file dialog (thread-safe, automatic title extraction).
  - Online schoolbook linking via `/link <URL>` or `/url` with `SchoolbookUrlModal` for title assignment.
  - Interactive commands listing via `/` in Schulbücher mode (`/link`, `/url`, `/unlink`, and existing books).
  - 1-Click opening: PDF in OS default viewer (`os.startfile`) and web links in browser (`webbrowser.open`).
  - Isolated persistence in `data/schoolbooks.json` protected from Git tracking via `.gitignore` and excluded from `git_sync_service.py`.
  - Full headless CLI integration via `tasks books [list|open|add|remove] [--json]`.
  - 12 comprehensive unit and integration tests in `tests/test_schoolbooks.py`.

- [x] **Digi4School Book Grabber Integration (Ultra-HD & Adaptive DPI Update)**:
  - Eingebauter Download-Befehl `/download` (Aliase `/d4s`, `/digi4school`) direkt in der Schulbuch-Suchleiste (`Backspace` -> `Tab`).
  - Schnelleingabe mit Zugangscode (z. B. `/download 26s7dbu5qxvw`) oder über die interaktive Befehlsliste (`/`).
  - **Ultra-HD Resolution als Standard (`scale=4.0`)**: Playwright rendert Seiten in gestochen scharfer 4K/Retina-Auflösung (~3.600 × 5.200 px).
  - **Adaptive DPI- & Geometrie-Normierung**: `effective_dpi = dpi or int(150 * scale)` skaliert auf 600 DPI bei Scale 4.0, während die physische PDF-Seitengröße (A4/B5) exakt erhalten bleibt.
  - Interaktiver Login-Dialog (`Digi4SchoolDownloadModal`) mit sofortiger Speicherbereinigung (`del password`), Tesseract-OCR-Prüfung und nativer **Render Quality Auswahl** (`Select`: `Ultra-HD 4.0x`, `High-Res 3.0x`, `Standard 2.0x`).
  - Live `ProgressBar`-Modal (`Digi4SchoolProgressModal`) mit Qualitäts-Badge (`QUALITY: ULTRA/HIGH/STANDARD`), Statusanzeige (Login, Seiten laden, OCR, Lesezeichen), präziser Restzeitanzeige (ETA) und rotem Warnbanner.
  - Generiert voll durchsuchbare OCR-Sandwich-PDFs mit Multi-Core LSTM Tesseract, hierarchischen Lesezeichen, Klick-Hyperlinks und synchronisierten Seitennummern (/PageLabels).
  - Speichert das PDF direkt in `%USERPROFILE%\Downloads\` mit 1-Klick-Button zum Öffnen des Zielordners.
  - Erweiterte Headless CLI-Optionen: `tasks books download <code> [--email <mail>] [--password <pw>] [--scale <float>] [--quality standard|high|ultra] [--dpi <int>] [--no-ocr] [--no-toc] [--page-offset auto|<int>] [--visible] [--tesseract-cmd <path>] [--json]`.
  - 13 automatisierte Unit- und CLI-Tests in `tests/test_digi4school.py` (100% Testabdeckung aller 182 Tests).

- [x] **Full English Application Localization**:
  - Audited and translated all UI screens, modals, dialogs, buttons, table headers, toasts, and CLI outputs to consistent English.
  - Translated CommandPalette badges (`Courses` / `Schoolbooks`), placeholders, search hints, and action commands (`/r`, `/link`, `/url`, `/download`, `/unlink`).
  - Translated all modals: `SchoolbookUrlModal`, `Digi4SchoolDownloadModal`, `Digi4SchoolProgressModal`, `TeamsSetupModal`, `LoginChoiceModal`, `GitSetupModal`, `AddExamModal`, and `ExcuseLetterModal` table headers (`Periods`, `{hours} periods`).
  - Localized Agent CLI (`agent_cli.py`): table headers (`PLATFORM`, `SUBJECT`, `COURSE NAME`, `DUE DATE`, `STATUS`, `TITLE`), error messages, and `tasks books` CLI outputs.
  - Localized core services (`license.py`, `auth.py`, `git_sync_service.py`, `digi4school_service.py`, `untis_service.py`, `schoolbook_service.py`, `moodle_service.py`, `teams_service.py`).
  - Maintained deliberate design boundaries: Official excuse letter PDF generation (`excuse_service.py`) remains in Austrian German for submission to HTL teachers; external data arriving from Moodle/Teams remains unmodified; dual-language web scrapers preserved.
  - Updated all unit test assertions across `tests/` with 100% test pass rate (all 179 tests pass).

- [x] **Privacy Audit, Data Anonymization & Git History Squash**:
  - Audited full codebase and documentation for personal data; eliminated hardcoded student email fallbacks (`end240102@spengergasse.at`) in `src/core/auth.py`, `src/ui/tui_app.py`, and `tests/test_untis_exams.py`.
  - Replaced personal profile data in `README.md` example configurations with anonymous standard placeholders (`Max Mustermann`, `1AHIT`, `my-school`).
  - Removed local Windows filesystem path links containing username (`xandi`) in favor of relative project documentation links.
  - Squashed Git commit history to a single clean root commit attributed to `Alexander Endl <X4nd109@users.noreply.github.com>`, completely purging historical commit diffs of student identifiers.
  - Force-pushed clean `main` and `v1.0.0` tags to GitHub.

- [x] **README Overhaul & Legal Notice**:
  - Fully translated [`README.md`](../README.md) to professional English matching project localization standards.
  - Added official Legal Disclaimer (§ 42 Austrian Copyright Act / UrhG personal study only, no DRM circumvention, prohibition of redistribution, trademark notices).
  - Confirmed and documented full compatibility between MIT License and legal study disclaimer.

- [x] **Missing Dependency Detection & Interactive Auto-Install**:
  - Implemented lightweight, zero-dependency pre-flight checker in `src/core/dependency_checker.py`.
  - Replaced silent fallback to legacy CLI with an English framed ASCII warning banner.
  - Displays missing requirements from `requirements.txt` with their respective roles.
  - Directly provides the exact Windows install command (`python -m pip install -r requirements.txt`).
  - Added interactive prompt (`[Y/n]`) automatically triggering pip installation in TTY environments and instantly launching the modern TUI upon success.
  - Eliminated automatic fallback to `interactive_loop()` in `src/main.py` while keeping `--cli` functional as an explicit flag.
- [x] **Theme Library Expansion & Header UI Refinement**:
  - Expanded curated theme library in `src/core/config.py` from 5 to 21 themes (added 16 new themes including Gruvbox, Rosé Pine variants, Solarized, Catppuccin variants, Atom One, Flexoki, Textual Dark/Light, and ANSI vintage).
  - Updated `ThemeSelectModal` in `src/ui/tui_app.py` with dynamic button mapping and `VerticalScroll` for smooth navigation across all 21 themes.
  - Refined the "Next Exam" header badge styling in `tui_app.py`: changed date and subject to vibrant blue (`bold dodger_blue1`) and countdown badge to green (`bold green`), replacing previous yellow and cyan.
- [x] **Favorite Themes via Right-Click (`⭐`)**:
  - Added persistent favorites configuration (`favorite_themes`) in `data/config.json` via `load_favorite_themes`, `save_favorite_themes`, and `toggle_favorite_theme` in `src/core/config.py`.
  - Implemented right-click toggle in both the `ThemeSelectModal` (using custom `ThemeButton`) and the Textual Command Palette (`FavoriteThemeProvider`, `ThemeCommandList`, `ThemeCommandPalette`).
  - Sorted all favorite themes to the very top of both theme menus, prefixed with a golden star (`⭐ `).
  - Integrated toast notifications on right-click ("Added to favorites ⭐" / "Removed from favorites") and in-place button reordering.
  - Full Git-Sync integration: `favorite_themes` are merged across devices in `git_sync_service.py` (`merge_config_files`) and changes trigger background auto-push.
- [x] **PyMuPDF Modern Import Migration & FutureWarning Elimination**:
  - Replaced legacy `import fitz` with modern `try: import pymupdf as fitz except ImportError: import fitz` in `src/services/digi4school_service.py` and `tests/test_excuse_service.py`.
  - Updated pre-flight dependency checker in `src/core/dependency_checker.py` and `setup.bat` to verify modern `pymupdf` with legacy `fitz` fallback.
  - Added warning suppression in `main.py` and `src/main.py` to prevent any sub-package `fitz` deprecation warnings from leaking to the terminal.
- [x] **Version Display & GitHub Release Update Reminder**:
  - Centralized application version (`APP_VERSION = "1.0.2"`) and repository reference (`GITHUB_REPO = "X4nd109/Aufgaben-Detector"`) in `src/core/config.py`.
  - Integrated version badge in `SettingsModal` (`[O]`) pinned to the top-right corner in bold white font (`v1.0.2`).
  - Created standalone `src/services/update_service.py` with semver tuple parser (`parse_version`, `is_newer_version`) and GitHub API release checking with zero external dependencies.
  - Designed `UpdateReminderModal` appearing in screen center upon startup when a newer GitHub release is detected, featuring current/new version tags and 1-click `🌐 Open Release in Browser` (`Enter`) and `↩️ Dismiss` (`ESC`).
  - Integrated non-blocking startup check via background daemon thread so instant `< 0.1s` offline app launch is preserved.
  - Added 9 comprehensive unit and UI tests in `tests/test_update_service.py` (total 206 tests passing with 100% success rate).

---

## 2. In Progress / Immediate Next Steps

- [ ] **Background Task Notifications**:
  - Optional Windows notification toast for assignments due within 24 hours.
- [ ] **Extended Test Coverage**:
  - Expand offline test fixtures for WebUntis multi-day holiday and substitution edge cases.
- [ ] **Git Synchronization Refinement**:
  - Enhance `git_sync_service.py` conflict resolution for user notes in `data/exam_notes.json`.

---

## 3. Known Issues & Blockers

- *None active* (All 206 test suite tests passing cleanly).

---

## 4. Session Handoff Notes (Context for Next Agent)

- **Recent Achievements (2026-10-18)**:
  - **Digi4School Grabber Sync & Ultra-HD Resolution Standard**:
    - Ported all enhancements from standalone `Digi4School_Book_Grabber` into `src/services/digi4school_service.py`.
    - Upgraded default rendering resolution to **Ultra-HD (`scale=4.0`)** via Playwright `device_scale_factor`.
    - Coupled OCR DPI dynamically (`effective_dpi = dpi or int(150 * scale)` $\rightarrow$ 600 DPI @ 4.0x, 300 DPI @ 2.0x) while retaining standard A4/B5 PDF geometry.
    - Added quality presets (`ultra`, `high`, `standard`), `--no-ocr` fast image fallback, `--no-toc`, and `--page-offset` controls.
    - Hardened credential security via immediate in-memory password disposal (`del password`).
  - **Interactive TUI Quality Dropdown**:
    - Added native `Select` widget to `Digi4SchoolDownloadModal` for choosing render quality prior to download.
    - Displayed active quality badge (`QUALITY: ULTRA/HIGH/STANDARD`) in `Digi4SchoolProgressModal`.
  - **CLI & Test Coverage**:
    - Enhanced `tasks books download` CLI flags (`--quality`, `--scale`, `--dpi`, `--no-ocr`, `--no-toc`, `--page-offset`, `--visible`).
    - Added 3 new unit tests in `tests/test_digi4school.py` (total 13 tests, whole suite 182 tests with 100% pass rate).
  - **Documentation & Architecture Records**:
    - Added ADR-012 in `docs/decisions.md` and updated `docs/features.md`, `docs/architecture.md`, and `docs/current-state.md`.
- **Localization Standard**:
  - All future UI elements, dialogs, modals, CLI outputs, toasts, and logging must be written in **English** (see `docs/conventions.md` & `ADR-010`). Only the generated excuse letter PDF remains in Austrian German.
- **Entry Points**:
  - Desktop / Interactive: `run.bat` or `python main.py`
  - Agent / Script: `tasks.bat <subcommand>` or `python main.py <subcommand>`
  - Digi4School CLI: `tasks books download <zugangscode> [--quality ultra|high|standard] [--json]`
- **Test Verification**:
  - Run all tests with `python -m unittest discover tests`.

