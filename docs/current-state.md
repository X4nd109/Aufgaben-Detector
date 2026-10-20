# Current Project State & Session Handoff — Aufgaben-Detector

> **Last Updated**: 2026-10-20  
> **Active Milestone**: Milestone 3 — In-App Auto-Update & High-DPI UI Polish (v1.0.6)

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

- [x] **Verzeichnis-Schnellzugriff & CommandPalette UX Fixes (v1.0.4)**:
  - Unified `Backspace` CommandPalette mit 3-Wege `Tab`-Umschaltung: **Courses** (Cyan) ➔ **Schoolbooks** (Rot) ➔ **Directories** (Grün).
  - Zentrierter Header-Schriftzug `[bold green]Directories[/bold green]` und dynamischer Such-Placeholder (`Search directories (/link, /unlink)...`).
  - **Suchtext-Erhalt bei Moduswechsel**: Eingegebener Text in der Suchleiste bleibt beim Wechseln mit `Tab` erhalten und filtert sofort im neuen Tab.
  - **Backspace-to-Close**: Wenn die Suchleiste leer ist, schließt ein Druck auf `Backspace` die Suchleiste sofort (`UnifiedCommandInput`).
  - Direkte Ordnerverknüpfung via `/link` über den nativen Windows-Ordnerauswahldialog (`FolderBrowserDialog` / `askdirectory`) mit automatischer Titelableitung vom Ordnernamen (z. B. `BET`).
  - 1-Klick / `Enter` zum Öffnen des verknüpften Ordners direkt im Windows Explorer (`os.startfile`).
  - Schnelles Löschen verknüpfter Ordner über `/unlink` oder `/delete`.
  - Lokale Persistenz in `data/directories.json` (automatisch von Git-Tracking ausgeschlossen via `.gitignore`).
  - Vollständige Headless CLI-Integration via `tasks dirs [list|open|add|remove] [--json]`.
  - **OLED Theme & UI Polish (22 Themes)**:
    - Neues `oled` Theme mit purem Schwarz (`#000000` Background/Surface/Panel) kombiniert mit Flexoki-Farbakzenten.
    - **Header & Bar Clipping behoben**: Borders von `Header`, `#info_bar` und `#button_bar` entfernt, damit Widgets und Buttons vertikal nicht mehr abgeschnitten werden.
    - **Button-Höhe wiederhergestellt**: Durch `height: 3;` in `.-theme-oled Button` besitzen Buttons in allen Menüs und Modals (`SettingsModal`, `ThemeSelectModal`, etc.) wieder die gewohnte 3-Zeilen-Höhe mit voller Lesbarkeit und zentrierter Schrift statt auf 1 Zeile zusammenzufallen.
    - **Weiße Spalten-Header**: Tabellen-Header (`DataTable > .datatable--header`) von Orange auf klares Weiß (`#ffffff`, bold) umgestellt.
    - **Tabellen-Fokus bleibt tiefschwarz**: Wenn mit `Tab` durch die Menüs (Main `#tasks_table`, Tests `#exams_table`, Absenzen `#abs_subject_table`/`#abs_detail_table`) navigiert wird, bleibt der Hintergrund rein schwarz (`background: #000000; background-tint: transparent;`) statt durch Textuals Default-Fokus-Tint grau aufzuleuchten.
    - **Theme-Menü Hover-State**: Beim Hovern über Themes in `ThemeSelectModal` wird der Hintergrund in dezentem Hellgrau (`#343331`) hervorgehoben.
  - 19 automatisierte Tests für Verzeichnisse und OLED-Theme-Styling.

- [x] **Windows-Tastatur-Shortcuts für alle Texteingabefelder (v1.0.5)**:
  - Projektweite Bereitstellung (`configure_enhanced_text_inputs`) für alle `Input`-Widgets (CommandPalette, Suchleisten, Formulare, Logins, Schulkonfiguration) und mehrzeilige `TextArea`-Notizen.
  - **STRG + A**: Markiert den gesamten Inhalt des Textfeldes (ersetzt Textuals Default `home`).
  - **Pos1 (`Home`) & Ende (`End`)**: Springt direkt an Zeilenanfang bzw. Zeilenende.
  - **SHIFT + Pos1 & SHIFT + Ende**: Markiert vom Cursor bis zum Zeilenanfang bzw. Zeilenende.
  - **STRG + ← & STRG + →**: Wortweises Springen des Cursors.
  - **SHIFT + STRG + ← & SHIFT + STRG + →**: Wortweises Markieren des Textes (`ctrl+shift+left` und `shift+ctrl+left`).
  - **STRG + Backspace & STRG + Entf**: Wortweises Löschen nach links bzw. rechts.
  - **STRG + Backspace 5-Stufen-Absicherungsarchitektur**:
    - Stufe 1 (Win32 Driver Patch): ConPTY KeyEvents mit `\x1b[127;5u`.
    - Stufe 2 (Hardware-Hook): OS-Abfrage (`GetAsyncKeyState(0x11)`).
    - Stufe 3 (CommandPalette Guard): `UnifiedCommandInput.action_delete_left`.
    - Stufe 4 (App-Level Menü Guard): Menü-Blockierung bei gedrücktem STRG.
    - Stufe 5 (Fallback Bindings): Native Terminal-Bindings.
  - 6 automatisierte Unit-Tests in `tests/test_tui_app.py` (insgesamt 230 Tests).

- [x] **Per-Monitor DPI-Awareness v2 & Native Windows Explorer Dialoge (v1.0.6)**:
  - Zentrales Modul `src/core/win_dialogs.py` mit `enable_high_dpi_awareness()`, `pick_file()` und `pick_directory()`.
  - Aktiviert `SetProcessDpiAwarenessContext(HANDLE(-4))` (Per-Monitor DPI Aware v2) direkt beim Programmstart (`main.py`, `src/main.py`), in `AufgabenApp.on_mount` und vor jedem Dialog.
  - Echte native Windows COM `IFileOpenDialog`-Instanzen für Dateiauswahl (`/link` in Schulbüchern) und moderne Ordnerauswahl mit `FOS_PICKFOLDERS` (`/link` in Verzeichnissen).
  - Volle Unterstützung für Schnellzugriff, Adressleiste, Suche und automatische 4K-Skalierung ohne bilineare DWM-Bitmap-Streckung („Low-Res-Explorer-Effekt“ behoben).
  - Graceful Fallback Cascade auf DPI-aware Tkinter und PowerShell Windows Forms.
  - 11 neue automatisierte Tests in `tests/test_win_dialogs.py`.

- [x] **Automatische 1-Klick In-App Update-Funktion im UpdateReminderModal (v1.0.7)**:
  - Vollautomatischer Download des Release-Installers (`AufgabenDetector_Setup.exe`) direkt im Modal mit Textual `ProgressBar`, Statusanzeige (MB/Gesamt-MB, Prozent) und Abbruchmöglichkeit (`cancel_event`).
  - Robuste Fehlerbehandlung mit Retry- und Fallback-Button ("Im Browser herunterladen").
  - **Zielordner- & Konfigurationserhalt**: Installation erfolgt zwingend im aktuellen Programmverzeichnis (`WORKSPACE_DIR`); `config.json`, `data/`, Caches und persönliche Einstellungen bleiben unberührt.
  - **Keine PATH-Modifikation**: Übergabe von `/NOTASKS=1` und `/UPDATE=1` an Inno Setup (`installer/aufgaben_detector.iss`) überspringt `setup_command.bat`, sodass die PATH-Variable unberührt bleibt.
  - **Automatisches Abhängigkeiten-Update**: `setup.bat /silent` prüft und installiert neue pip requirements im Hintergrund ohne blockierende Pause-Abfragen.
  - **Entkoppelter Handoff & Auto-Neustart**: `%TEMP%\AufgabenDetector_Update\apply_update.cmd` wartet auf Beenden des Python-Prozesses, führt die Aktualisierung geräuschlos (`/VERYSILENT`) durch und startet `run.bat` neu.
  - 5 neue automatisierte Tests in `tests/test_update_service.py` (insgesamt 246 Tests in der Testsuite mit 100% Erfolgsquote).

- [x] **DPI-Fensterproportionen & Settings-Modal UX Fix**:
  - **Terminal-Startgröße**: `ensure_terminal_window_size` auf 123 Spalten (+1 Spalte breiter) und 33 Textzeilen (-3 Zeilen niedriger) feinjustiert.
  - **DPI-Höhenskalierung**: Höhe wird unter Berücksichtigung von `GetDpiForWindow` und gemessener Zeilenhöhe dynamisch auf 33 Textzeilen (`effective_min_h`) skaliert.
  - **ExamsScreen Vollbreiten-Spaltenverteilung & Beseitigung des rechten Leerraums**:
    - Alle 9 Spalten werden dynamisch und proportional über die gesamte Containerbreite gestreckt (`dt.columns[i].width`), sodass rechts kein ungenutzter schwarzer Bereich mehr entsteht und der blaue Zeilen-Cursor die gesamte Breite hervorhebt.
    - Themen/Notizen erhalten bei breiten Bildschirmen bis zu 60 % des zusätzlichen Freiraums (keine unnötigen `...`-Kürzungen mehr).
    - Vertikaler Scrollbar-Puffer verhindert horizontales Scrollen bei jeder Fenstergröße.
    - Vollständige dynamische Größenanpassung via `on_resize(term_w_override=...)`.
    - Neuer Test `test_exams_screen_full_width_column_distribution_and_resize` (Gesamtsuite: 247 bestandene Tests mit 100% Erfolgsquote).
  - **SettingsModal Button-Clipping behoben**: `#settings_dialog` auf `VerticalScroll` umgestellt, Button-Abstände (`margin-bottom: 1;`, `padding: 1 2;`) exakt an `FilterMenuModal` angeglichen und maximale Höhe auf `96%` erweitert. Der `[↩️ Close [ESC]]`-Button wird nicht mehr abgeschnitten und bleibt jederzeit voll sichtbar und erreichbar.
  - **FilterMenuModal Bereinigung**: Die redundante Textzeile (`#filter_info`) unter dem Titel („Status: ... | Due Window: ...“) wurde entfernt, da die Zustände bereits auf den Buttons abgebildet werden.

- [x] **Main Task Dashboard Vollbreiten-Spaltenverteilung & Beseitigung der Scrollleiste (v1.0.8)**:
  - Dynamische proportionale Breitenberechnung aller 7 Spalten (`#`, `Platform`, `Subject`, `Assignment`, `Due Date`, `Status`, `Teacher`) basierend auf der tatsächlichen Fenster-/Container-Breite analog zum Exams-Screen.
  - Spaltenbreiten werden explizit auf den `DataTable`-Spalten gesetzt (`col.width`, `auto_width = False`), wodurch die Tabelle 100 % der Fensterbreite ausfüllt und horizontaler Überlauf sowie die Scrollleiste vollständig eliminiert werden.
  - Spalte *Assignment* erhält den flexiblen Mittelteil der Breite und wird bei Überschreitung sauber mit `...` (3 ASCII-Punkte) gekürzt (z. B. `OverTheWire/Bandit_0-6_Linux...`).
  - Zeilenumbrüche und Whitespace-Spitzen in Titeln und Notizen werden vor der Darstellung bereinigt, um Mehrzeiligkeit oder Formatierungsbrüche zu verhindern.
  - Reagiert sofort auf Terminalgrößenänderungen via `on_resize(term_w_override=...)`.
  - **Moodle-Status-Negationsprüfung**: Negationsabsicherung in `Task.is_completed` und `format_status_english`: Texte wie *„Bisher wurden keine Aufgaben abgegeben“* oder *„nicht abgegeben“* werden nicht mehr fälschlicherweise durch das Teilwort *„abgegeben“* als erledigt gewertet, sondern bleiben korrekt als `Open` erhalten.
  - 3 neue automatisierte Tests in `tests/test_tui_app.py` (insgesamt 249 Tests in der Gesamtsuite mit 100 % Erfolgsquote).

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

- *None active* (All 249 test suite tests passing cleanly with 100% pass rate).

---

## 4. Session Handoff Notes (Context for Next Agent)

- **Recent Achievements (2026-10-20 — Main Dashboard Dynamic Columns & Assignment Truncation)**:
  - Vollständige dynamische Spaltenanpassung auf 100 % Containerbreite ohne horizontale Scrollleiste.
  - Sauberes Truncating langer Angaben mit `...` (z. B. `OverTheWire/Bandit_0-6_Linux...`).
  - Negationsabsicherung für Moodle-Statustexte (*"keine Aufgaben abgegeben"*).
  - 249 Tests in der Gesamtsuite mit 100 % Erfolgsquote.
- **Previous Achievements (2026-10-20 — v1.0.7 In-App Auto-Update Feature)**:
  - 1-Click Auto-Update Flow (`UpdateReminderModal`) mit Chunk-Download, Fortschrittsanzeige und geräuschlosem Inno Setup Handoff.
- **Entry Points**:
  - Desktop / Interactive: `run.bat` oder `python main.py`
  - Agent / Script: `tasks.bat <subcommand>` oder `python main.py <subcommand>`
- **Test Verification**:
  - Run all tests with `python -m unittest discover tests`.
