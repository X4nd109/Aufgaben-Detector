# Current Project State & Session Handoff — Aufgaben-Detector

> **Last Updated**: 2026-10-22  
> **Active Milestone**: Milestone 4 — AI Explain, Agentic Coding Tool Integration & Desktop App Linking (v1.2.0)

---

## 1. Completed Tasks & Milestones

- [x] **Release v1.2.0 — AI Explain, Agentic Coding Tool Integration & Desktop App Linking**:
  - **'Ai Explain' Button & Workflows (`TaskDetailModal`, `AiExplainModal`, `open_ai_explain`)**:
    - Strukturierte Prompts auf Deutsch oder Englisch mit allen Aufgabenmetadaten und Dateianhängen.
    - Automatisches Multi-Level Kopieren in die Windows-Zwischenablage (`pyperclip` + `ctypes` Fallback).
    - Browser-Link mit dynamischer Query-Param-Ersetzung (`{prompt}`) oder direktem Einfügen.
    - Vordefiniertes Preset `Desktop App` zum Starten lokaler KI-Anwendungen (`.exe`) via nativem Windows Dateidialog (`pick_file`).
    - Scrollbarer Dialog (`VerticalScroll`) mit `scrollbar-gutter: stable` und `max-height: 85%` gegen Button-Clipping.
    - Vollständige englische Lokalisierung der Benutzeroberfläche und Einstellungsdialoge.
  - **'Agent' Button & Agentic Coding Tool Workflow (`TaskDetailModal`, `AiAgentConfigModal`)**:
    - 1-Klick-Workflow lädt Aufgaben-Dateien & `angabe.md` in frei wählbaren Ordner via Windows Folder Picker herunter.
    - Kopiert automatisch den absoluten Projektpfad in die Windows-Zwischenablage (`Strg+V` im Coding Tool).
    - Startet das konfigurierte Agentic Coding Tool (Antigravity, Cursor, VS Code etc.) als unabhängigen Hintergrundprozess.
  - **Zentralisiertes 'AI Configuration' Einstellungsmenü (`AiConfigChoiceModal` & `AiAgentConfigModal`)**:
    - Zusammenfassung von AI Explain und AI Agent unter `🤖 AI Configuration` (Shortcut `[7]` / `[A]`).
    - Modale Verwaltung der Executable mit Explorer-Auswahl und Zurücksetzen-Funktion.
  - **Headless Agent CLI Subcommands (`tasks explain`, `tasks agent`)**:
    - Direkte Terminal- und JSON-Schnittstelle für autonome Agenten und Skripte.
  - 23 neue automatisierte Unit-Tests (Gesamtsuite: 317 Tests, 100 % Erfolgsquote).

- [x] **Feature: 'Agent' Button & 'AI Configuration' Hub (TUI & Headless CLI)**:
  - **Interaktiver 'Agent'-Button (`TaskDetailModal`)**:
    - Neuer Button `#btn_det_agent` (`🤖 Agent [G]`) in der Aufgaben-Detailansicht mit Shortcut `[G]`.
    - Öffnet den Windows-Folder-Picker (`pick_directory`), sodass der Benutzer sein gewünschtes Projektverzeichnis frei wählen kann.
    - Lädt alle Anhänge und die formatierte Aufgabenstellung (`angabe.md`) direkt in den Zielordner herunter.
    - Kopiert automatisch den absoluten Projektpfad in die Windows-Zwischenablage (`Strg+V` im Coding Tool).
    - Startet das konfigurierte Agentic Coding Tool als eigenständigen Hintergrundprozess (ohne erzwungene Projekt-Neuerstellung).
    - Falls kein Tool hinterlegt ist, erscheint eine In-App Notification mit Hinweis auf die Settings.
  - **Zentrales Einstellungs-Hub `AI Configuration` (`SettingsModal`, `AiConfigChoiceModal`, `AiAgentConfigModal`)**:
    - Zusammenführung von 'AI Explain' und 'AI Agent' unter `🤖 AI Configuration` (Shortcut `[7]` / `[A]`).
    - `AiConfigChoiceModal`: Übersichtliches Menü zur Verzweigung in Explain- oder Agent-Einstellungen.
    - `AiAgentConfigModal`: Anzeige der konfigurierten Tool-Executable, Durchsuchen per Windows Datei-Explorer (`pick_file`) und Reset-Funktion.
    - Persistente Speicherung in `config.json` unter `agent_coding_tool_path`.
  - **Headless Agent CLI (`tasks agent`)**:
    - `tasks agent <id|index> [--dir <pfad>] [--no-launch] [--json]`.
  - 9 neue automatisierte Unit-Tests in `tests/test_agent_feature.py` (Gesamtsuite: 315 bestandene Tests mit 100 % Erfolgsquote).

- [x] **Feature: 'Ai Explain' Integration (TUI & Headless CLI)**:
  - **Interaktiver Button in der Detailansicht (`TaskDetailModal`)**:
    - Neuer Button `#btn_det_ai_explain` (`🤖 Ai Explain [A]`) neben Download [D] / Mark as Open [E].
    - Shortcut `[A]` löst die Erklärung direkt per Tastatur aus.
    - Funktioniert nahtlos für alle Aufgabenarten (Moodle, Teams und manuell erstellte Aufgaben).
  - **Automatischer KI-Prompt mit Metadaten & Dateiliste (`build_ai_explain_prompt`)**:
    - Strukturierter Aufbau mit Aufgabenstellung, Fach, Titel, Fälligkeit, Lehrkraft, Beschreibung und Angabe-Details.
    - Listet alle dazugehörigen Dateianhänge auf, damit die KI über alle Aufgabendokumente im Bilde ist.
    - Umschaltbar auf Deutsch ("Erkläre mir folgende Schulaufgabe...") oder Englisch ("Please explain the following school assignment...").
  - **Multi-Level Clipboard-Integration (`copy_to_clipboard`)**:
    - Legt den generierten Prompt sofort in die Windows-Zwischenablage (pyperclip mit ctypes user32/kernel32 und clip.exe Fallback).
  - **Browser-Integration & URL-Templates (`open_ai_explain`)**:
    - Unterstützt direkte Query-Param-Übergabe via `{prompt}` (z. B. ChatGPT oder Perplexity).
    - Unterstützt Direktlinks (z. B. Google Gemini, wo einfaches `Strg+V` im geöffneten Chatfenster genügt).
  - **Konfigurations-Modal in den Einstellungen (`AiExplainModal` / `SettingsModal`)**:
    - Neuer Menüpunkt `#btn_set_ai_explain` (`🤖 AI Explain Config [6]`).
    - Schnellauswahl vorkonfigurierter Provider (Google Gemini, ChatGPT, Perplexity, Eigene URL).
    - 1-Klick Umschaltung der Prompt-Sprache (Deutsch / Englisch).
    - Persistente Speicherung in `config.json` unter `ai_explain_config`.
  - **Headless Agent CLI (`tasks explain`)**:
    - `tasks explain <id|index> [--lang de|en] [--copy-only] [--no-browser] [--json]`.
  - 11 neue automatisierte Unit-Tests in `tests/test_ai_explain.py` (Gesamtsuite: 306 bestandene Tests).

- [x] **Release v1.1.0 — WebUntis Lateness & Excuse Letter Polish, Login Reminder & Platform Toggle**:
  - **Minutengenaue Verspätungs- & Fehlzeitenberechnung**:
    - `match_absences_with_timetable` ermittelt für Verspätungen (z.B. eingetragene 11 oder 25 Minuten) die exakte minutengenaue Schnittmenge (`start_time`, `end_time`, `duration_minutes`) und behält das Unterrichtsfenster (`lesson_start_time`, `lesson_end_time`) bei.
    - Die Detailtabelle im `AbsencesScreen` zeigt in der Spalte `Time` das reale Abwesenheitsintervall (z.B. `14:25 - 14:36`).
    - `get_daily_absence_summaries` und `create_excuse_pdf` summieren die tatsächliche Abwesenheitsdauer exakt (z.B. `7:16` statt pauschal `8:20`).
  - **Verspätungen-Filterbutton (`ExcuseLetterModal`)**:
    - Neuer Toggle-Button `#btn_el_filter_lateness` (`⏳ Hide Lateness: ON` / `⏳ Hide Lateness: OFF`, Shortcut `[L]`) in der rechten unteren Ecke.
    - Standardmäßig aktiv: Filtert Fehltage mit einer Dauer von unter 50 Minuten (`< 50 min`) automatisch aus, sodass standardmäßig nur vollwertige Fehlstunden im Entschuldigungs-PDF aufgeführt werden.
    - Behoben: `Back`-Button im `ExcuseLetterModal` kehrt unmittelbar zum `AbsencesScreen` zurück ohne versehentliches Öffnen des Schülerdaten-Modals.
  - **Plattform-Deaktivierung & Abmelden im Login-Menü (`LoginChoiceModal`)**:
    - Kombinierter Action-Button (`Enable` / `Disable` / `🚪 Log Out`) am rechten Rand.
    - Leeren von Cache und Credentials bei Abmeldung; Deaktivieren schaltet Sync und Erinnerungen für ungenutzte Plattformen stumm.
    - Persistente Speicherung in `config.json` unter `enabled_platforms`.
  - **Humanisierte Netzwerk-Fehlerbehandlung & Fast-Fail**:
    - `_humanize_request_error` fängt rohe urllib3/requests Tracebacks ab und gibt präzise englische Fehlermeldungen aus.
    - Schneller Abbruch bei Serverausfällen ohne 15s Playwright-Wartezeit.
    - Neutraler Platzhalter `"Username"` und Bereinigung der E-Mail-Vorausfüllung in Teams.
  - **Login-Prüfung & LoginReminderModal bei jedem Sync**:
    - Automatischer Reminder am Ende eines Syncs, falls genutzte Plattformen nicht angemeldet sind, mit direkter Weiterleitung per Enter ins Login-Menü.
  - 18 neue automatisierte Unit-Tests in `tests/test_auth_logins.py`, `tests/test_excuse_service.py`, `tests/test_tui_app.py` und `tests/test_untis_service.py` (Gesamtsuite: 294 Tests, 100 % Erfolgsquote).

- [x] **Moodle & WebUntis Login Robustness & Cross-Device Compatibility**:
  - **Browserloses HTTP-Moodle-Login (`login_moodle_http`)**:
    - Moodle-Authentifizierung läuft primär über direkte HTTP-Requests (`requests.Session` mit dynamischer `logintoken`-Extraktion und Form-POST).
    - Funktioniert in unter 0,3s ohne vorinstallierten Playwright-Chromium-Browser (löst Login-Fehlschläge auf Geräten, auf denen nur `pip install -r requirements.txt` ausgeführt wurde).
    - Automatischer Browser-Fallback (`chrome`, `msedge`, `chromium`) nur noch als sekundäre Stufe für Notfälle.
  - **WebUntis Schulsuche & Bereinigung (`search_webuntis_school`, `clean_school_identifier`)**:
    - Automatische Erkennung und Bereinigung von Domains (`spengergasse.webuntis.com`), vollständigen URLs und Leerzeichen.
    - Integration der offiziellen WebUntis School Search API (`https://mobile.webuntis.com/ms/schoolquery2`).
    - Wenn das Schulfeld im Dialog leer gelassen wird, wird automatisch die Standard-Schule (`spengergasse`) verwendet.
  - **Automatisches Bereinigen von Schul-E-Mail-Adressen (`clean_school_username`)**:
    - Falls Schüler ihre E-Mail-Adresse (`end240102@spengergasse.at`) statt der Schülerkennung eingeben, wird das Suffix `@...` automatisch entfernt.
  - **Präzise Fehlerrückmeldung im TUI**:
    - `AuthResult` Tuple-Klasse transportiert den echten Server-Fehlertext von Moodle und WebUntis direkt in die Statuszeilen von `MoodleLoginModal` und `UntisSetupModal`.
  - **Playwright Chromium Pre-Flight Prüfung im `dependency_checker`**:
    - Erkennt fehlende Browser-Binärdateien und stellt diese bei Bedarf bereit.
  - 7 neue automatisierte Unit-Tests in `tests/test_auth_logins.py` (Gesamtsuite: 274 Tests, 100 % Erfolgsquote).

- [x] **Sync Performance & TUI Lag Optimization (v1.0.10)**:
  - **SyncSpinner Interval Throttling**: TUI-Ladeanimation (`SyncSpinner`) von aggressiven 80 ms (12,5 FPS) auf 250 ms (4 FPS) gedrosselt. Verhindert die Überlastung des Textual Asyncio-Event-Loops und von Windows ConPTY ANSI-Rerenders bei gleichzeitiger Hintergrundarbeit.
  - **Batch-UI-Aktualisierung & Throttling**: Entkopplung der Daten-Tabelle via `update_info_bar()`. Mehrere schnell aufeinanderfolgende Sync-Callbacks von Moodle und Teams leeren und zeichnen die 40+ Zeilen der `DataTable` nur maximal einmal alle 0,8 Sekunden neu; dazwischen wird lediglich die Info-Statistikzeile aktualisiert.
  - **Entsperrte Cache-Persistenz & Batch-Disk-Writes**: `TaskManager.save_cache()` kopiert den Speicherzustand unter Lock und schreibt atomar auf die Festplatte *ohne* Lock, wodurch kein anderer Thread blockiert wird. Im Hintergrund-Prefetcher (`_prefetch_worker`) werden Cache-Saves auf alle 5 Aufgaben gebündelt statt nach jeder einzelnen Aufgabe.
  - **Playwright Headless Chromium Optimierung**: `--disable-gpu`, `--disable-dev-shm-usage`, `--renderer-process-limit=2` und Muting zu den Chromium-Headless-Flags hinzugefügt, wodurch die CPU-Last des Teams-Syncs minimiert wird.
  - **Mouse-Back-Listener Schlafpause**: Polling-Intervall in `_run_mouse_back_listener` von 25 ms auf 60 ms relaxiert.

- [x] **In-Terminal Update-Workflow & Getting-Started Restoration (v1.0.10 Polish)**:
  - **Getting-Started Wiederherstellung bei Updates**: `TaskManager._check_and_apply_version_update` erkennt Versions-Updates (via `data/version.json` oder In-App Update Marker), entfernt `manual_welcome_setup_guide` aus `deleted_manual_ids`, setzt den Status auf `Open` zurück und platziert die Aufgabe an erster Stelle.
  - **Button-zentrierte englische Anleitung**: Sämtliche Hotkey-Angaben wurden durch präzise Bezeichnungen der realen Textual UI-Buttons ersetzt (`⚙️ Settings`, `⚙️ School & Student Config`, `🔑 Login`, `👥 Teams Login`, `🎓 Moodle Login`, `📅 WebUntis Login`, `🐙 Git Cloud-Sync`, `🔄 Sync`, `✓ Mark as Completed`, `🗑️ Delete`).
  - **Keine redundante Bibliotheksinstallation**: `setup.bat /silent` wurde aus dem Update-Prozess entfernt, da `dependency_checker.py` fehlende Abhängigkeiten automatisch beim App-Start prüft und installiert.
  - **In-Terminal Update-Loop in `run.bat`**: `run.bat` fängt den Exit-Code `42` sowie `%TEMP%\AufgabenDetector_Update\pending_update.txt` ab, führt das Update via `start /wait` im aktuellen Konsolenfenster stillschweigend aus und startet die App direkt im selben Terminal neu (ohne PowerShell-Popups oder neue Konsolenfenster).
  - 3 neue automatisierte Unit-Tests in `tests/test_update_service.py` (Gesamtsuite: 267 bestandene Tests mit 100 % Erfolgsquote).

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

- [x] **UpdateReminderModal Englisch-Lokalisierung, Button-Layout & Text-Clipping (v1.0.8 Polish)**:
  - **Vollständige englische Lokalisierung**: Alle Textbausteine des Update-Erinnerungsmodals auf Englisch umgestellt (`🚀 New Version Available!`, `Current Version: ...`, `Latest Version: ...`, `A newer release with improvements and bug fixes is available on GitHub.`, `Initializing download...`, `Connecting to GitHub...`, `Downloading: ... MB / ... MB`, `Download complete! Preparing installation...`, sowie Fehlermeldungen).
  - **2-Zeilen-Button-Layout**: Der `Later [ESC]`-Button ist nun unter den beiden Haupt-Aktionen (`⬇️ Install Update Now` und `🌐 View in Browser`) zentriert platziert, sodass kein Button mehr am Dialogrand abgeschnitten wird.
  - **Analoges Error-Buttons-Layout**: Auch im Fehlerzustand sind die Optionen auf 2 Zeilen aufgeteilt (`🔄 Try Again` + `🌐 Download in Browser` oben, `Close [ESC]` zentriert unten).
  - **Beseitigung des Text-Clippings**: `width: 100%` auf `#update_hint` gesetzt, wodurch der Hinweistext automatisch sauber mehrzeilig umbrochen wird. Dialogbreite leicht auf 70 Spalten vergrößert für entspannte Ränder.
  - Maskierung der `\[ESC]`-Klammern, damit Textuals Content/Rich-Markup-Parser die Tastenkombination nicht verschluckt.
  - Neuer Test `test_update_reminder_modal_layout_and_english_texts` in `tests/test_update_service.py` (insgesamt 250 Tests in der Gesamtsuite mit 100 % Erfolgsquote).

- [x] **Tesseract OCR-Optimierung für Fett- und Unterstrichenen Text (v1.0.9)**:
  - **Sauvola Binarisierung (`thresholding_method=2`)**: Lokale adaptive Schwellenwertbildung verhindert das Zulaufen dicker Buchstabenschlaufen und trennt Unterstreichungen sauber vom Grundtext.
  - **Nicht-lineare Strichdicken-Normierung (`classify_nonlinear_norm=1`)**: Präzise Klassifizierung fetter Schriftzüge ohne Einstufung als Fremdsymbole.
  - **Unterstreichungstrennung (`textord_restore_underlines=1` & `textord_underline_threshold=0.5`)**: Horizontale Linien werden gezielt von Unterlängen (`g`, `j`, `p`, `q`, `y`) abgeschnitten.
  - **Sanftes Unsharp-Masking**: Schärfung vor Tesseract (`radius=1.2, percent=115, threshold=3`) für optimale Kantenpräzision ohne visuelle Einbußen im PDF.
  - Robuster doppelter Fallback auf Standard-OCR und reine Bild-Einbettung bei inkompatiblen Tesseract-Versionen.

- [x] **Digi4School Interaktive Seitenauswahl & 2-Thumb Range-Slider (v1.0.9)**:
  - **Automatische Buch- & Seitenzahlerkennung**: Neue Methode `Digi4SchoolService.inspect_book` loggt sich headless im Hintergrund ein und liest Buchtitel sowie die exakte Gesamtzahl der Buchseiten aus.
  - **Ladedialog `Digi4SchoolDetectModal`**: Kompakte Ladeanzeige (*"Connecting to Digi4School and detecting book pages..."*) mit Lade-Spinner und Abbrechen-Möglichkeit.
  - **Kompaktes Menü `Digi4SchoolPageRangeModal`**: Grafischer Auswahldialog für den gewünschten Seitenbereich mit Buchtitel, Zugangscode, 2-Thumb-Slider, synchronisierten Ziffernfeldern und zentriertem *All*-Button.
  - **Interaktives `TwoThumbRangeSlider` Widget**:
    - Stellt eine visuelle Schiene mit 2 Schiebern (Startseite und Endseite) im Catppuccin Mocha-Design dar.
    - Volle Mausbedienung (Klick auf Schiene zur Positionierung des nächstgelegenen Griffs sowie Halten und Ziehen per Drag & Drop).
    - Tastaturnavigation mit Pfeiltasten (`Left`/`Right`, `Shift` für 10er-Schritte, `Tab`/`1`/`2` zum Wechseln des aktiven Schiebers, `Home`/`End`).
  - **Synchronisierte Ziffernfelder**: Zwei Eingabefelder (*"From Page"* und *"To Page"*) zur Direkteingabe; bidirektional in Echtzeit mit dem Schieberegler synchronisiert.
  - **Range-Download & OCR**: Nahtlose Weitergabe des gewählten Seitenbereichs (z. B. `20-50`) an `Digi4SchoolProgressModal` und `Digi4SchoolService.download_book`.
  - 12 neue automatisierte Unit-Tests in `tests/test_page_range_slider.py` (insgesamt 264 Tests in der Gesamtsuite mit 100 % Erfolgsquote).

- [x] **Main Task Dashboard Formatierung, Sync-Uhrzeit & Spaltenpriorisierung (v1.0.9 Polish)**:
  - **Kein Zeilenumbruch der Sync-Uhrzeit**: `#info_bar` und `#info_stats` auf feste `height: 1` gesperrt mit `overflow-y: hidden`, `overflow-x: hidden` und `margin-bottom: 1;`, wodurch die gewohnte leere Trennzeile zwischen Info-Leiste und Aufgaben-Tabelle erhalten bleibt.
  - **Zero-Layout-Shift Sync-Spinner**: `SyncSpinner` besitzt nun eine permanent feste Boxbreite (`width: 3; height: 1; display: block;`). Das Starten und Stoppen des Hintergrund-Syncs verändert die verfügbare Breite um 0 Zeichen, wodurch das Springen der Uhrzeit (`19:09:06`) in eine zweite Zeile vollständig eliminiert wurde.
  - **Dynamisches Badge-Kompaktieren**: Bei schmaleren Terminalbreiten (< 118 Spalten) oder langen Prüfungs-Badges werden 0-Zähler (`Teams: 0`, `Manual: 0`) automatisch ausgeblendet und Trennzeichen gestrafft, damit die Sync-Anzeige niemals abgeschnitten wird.
  - **Header-Truncation "Teacher" behoben**: Spalte 6 (`Teacher`) von Basisbreite 6 auf min. 8 (bzw. 7 bei extrem schmalen Fenstern) erhöht, sodass der Header `"Teacher"` niemals zu `"Teache"` abgeschnitten wird und Lehrerkürzel voll lesbar bleiben.
  - **Priorisierte Spaltenbreitenverteilung**:
    - Spalte *Due Date* erhält garantierte 28–32 Zeichen für vollständige Datumsangaben (z. B. `Montag, 2. November, 23:59`) ohne unschöne `...`-Kürzungen.
    - Spalte *Teacher* erhält min. 8 Zeichen für Header und Lehrerkürzel.
    - Spalte *Assignment* nimmt den gesamten flexiblen Rest ein (`avail_content - sum(others)`) und wird bei Verkleinerung des Fensters als erste Spalte gekürzt.
  - **4K/1440p Startup Viewport-Kalibrierung**: In `_sync_initial_viewport` wird `refresh_table()` nach dem initialen UI-Mount erneut aufgerufen, sodass die exakten gemessenen Fensterdimensionen auf hochauflösenden Displays sofort greifen.
  - 2 neue automatisierte Tests in `tests/test_tui_app.py` (insgesamt 252 Tests in der Gesamtsuite mit 100 % Erfolgsquote).

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

- *None active* (All 317 test suite tests passing cleanly with 100% pass rate).

---

## 4. Session Handoff Notes (Context for Next Agent)

- **Recent Achievements (2026-10-22 — Release v1.2.0: AI Explain, AI Agent & AI Configuration Hub)**:
  - **'Ai Explain' Integration (`TaskDetailModal`, `AiExplainModal`, `open_ai_explain`)**:
    - Generiert strukturierte Prompts auf Deutsch oder Englisch mit allen Aufgabenmetadaten und Dateianhängen.
    - Automatisches Kopieren in die Zwischenablage (`pyperclip` + `ctypes` Fallback) und Öffnen im Browser oder Starten einer lokalen Desktop-App (`.exe`).
    - Vollständige englische Lokalisierung und dynamische Umschaltung zwischen Web-URL und Desktop-App-Pfad.
    - `VerticalScroll`-Unterstützung mit `scrollbar-gutter: stable` und `max-height: 85%`, wodurch die Buttons `Save [S]` und `Back [ESC]` auch in kompakten Terminals mit sicherem Puffer erreichbar sind.
  - **'Agent' Button & Agentic Coding Tool Integration (`TaskDetailModal`, `AiAgentConfigModal`, `run_agent_workflow`)**:
    - 1-Klick-Workflow lädt Aufgaben-Dateien & `angabe.md` herunter, kopiert den Zielordner-Pfad in die Zwischenablage und startet das konfigurierte Coding Tool (Antigravity, Cursor, VS Code etc.).
    - Native Windows-Explorer-Auswahl für Verzeichnisse (`pick_directory`) und Executables (`pick_file`).
  - **Zentrales Einstellungs-Hub `AI Configuration` (`SettingsModal`, `AiConfigChoiceModal`)**:
    - Menüpunkt in den Settings unter Shortcut `[7]` / `[A]`.
  - **Headless Agent CLI (`tasks explain`, `tasks agent`)**:
    - Vollständige Befehle für autonome KI-Agenten mit `--json`, `--copy-only`, `--no-launch` etc.
  - **316 automatisierte Tests** in der Gesamtsuite mit 100 % Erfolgsquote (`tests/test_ai_explain.py`, `tests/test_agent_feature.py`, `tests/test_tui_app.py` etc.).
- **Previous Achievements (2026-10-21 — Release v1.1.0 & WebUntis Lateness & Excuse Letter Polish)**:
  - Minutengenaue Verspätungsberechnung und Stundenplan-Abgleich.
  - Verspätungsfilter `Hide Lateness` im Entschuldigungs-Dialog.
  - Plattform-Toggle im Login-Menü.
- **Entry Points**:
  - Desktop / Interactive: `run.bat` oder `python main.py`
  - Agent / Script: `tasks.bat <subcommand>` oder `python main.py <subcommand>`
- **Test Verification**:
  - Run all tests with `python -m unittest discover tests`.
