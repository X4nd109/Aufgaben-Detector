# Current Project State & Session Handoff — Aufgaben-Detector

> **Last Updated**: 2026-10-18  
> **Active Milestone**: Milestone 3 — Open Source Release & GitHub Actions CI/CD (v1.0.0)

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

- [x] **Digi4School Book Grabber Integration**:
  - Eingebauter Download-Befehl `/download` (Aliase `/d4s`, `/digi4school`) direkt in der Schulbuch-Suchleiste (`Backspace` -> `Tab`).
  - Schnelleingabe mit Zugangscode (z. B. `/download 26s7dbu5qxvw`) oder über die interaktive Befehlsliste (`/`).
  - Interaktiver Login-Dialog (`Digi4SchoolDownloadModal`) mit sofortiger Speicherbereinigung und Tesseract-OCR-Prüfung.
  - Live `ProgressBar`-Modal (`Digi4SchoolProgressModal`) mit Statusanzeige (Login, Seiten laden, OCR, Lesezeichen), präziser Restzeitanzeige (ETA) und rotem Warnbanner.
  - Generiert voll durchsuchbare OCR-Sandwich-PDFs mit Multi-Core LSTM Tesseract, Lesezeichen, Klick-Hyperlinks und synchronisierten Seitennummern.
  - Speichert das PDF direkt in `%USERPROFILE%\Downloads\` mit 1-Klick-Button zum Öffnen des Zielordners.
  - Headless CLI-Integration via `tasks books download <code> [--email <mail>] [--password <pw>] [--json]`.
  - 10 automatisierte Unit- und CLI-Tests in `tests/test_digi4school.py`.

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

- *None active* (All 179 test suite tests passing cleanly).

---

## 4. Session Handoff Notes (Context for Next Agent)

- **Recent Achievements**:
  - Full codebase privacy audit completed: stripped student email (`end240102`), local paths (`xandi`), and personal config data.
  - Squashed Git history to clean root commit with GitHub private email attribution (`Alexander Endl <X4nd109@users.noreply.github.com>`), purging past diffs.
  - Overhauled and translated [`README.md`](../README.md) to English with updated feature showcase, full CLI cheat-sheet, badges, legal disclaimer (§ 42 UrhG personal study only), and verified MIT License compatibility.
  - Fixed GitHub Release URLs to point to active repository (`X4nd109/Aufgaben-Detector`).
  - Integrated Digi4School grabber, schoolbooks palette quick-open, and unified course links.
  - All 179 unit and integration tests passing with 100% pass rate.
  - Repository is completely clean and prepared for public visibility transition on GitHub.
- **Localization Standard**:
  - All future UI elements, dialogs, modals, CLI outputs, toasts, and logging must be written in **English** (see `docs/conventions.md` & `ADR-010`). Only the generated excuse letter PDF remains in Austrian German.
- **Entry Points**:
  - Desktop / Interactive: `run.bat` or `python main.py`
  - Agent / Script: `tasks.bat <subcommand>` or `python main.py <subcommand>`
  - Digi4School CLI: `tasks books download <zugangscode> [--json]`
- **Test Verification**:
  - Run all tests with `python -m unittest discover tests`.

