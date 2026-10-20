# Changelog — Aufgaben-Detector

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/)
und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

---

## [Unreleased]

---

## [1.0.9] - 2026-10-20

### Added
- **Tesseract OCR-Optimierung für Fett- und Unterstrichenen Text**:
  - **Sauvola Binarisierung (`thresholding_method=2`)**: Lokale adaptive Schwellenwertbildung verhindert das Zulaufen fetter Buchstaben und isoliert Unterstreichungen sauber von Grundlinien.
  - **Nicht-lineare Strichdicken-Normierung (`classify_nonlinear_norm=1`)**: Skaliert Buchstabenzüge basierend auf Strichdichte, sodass fette Wörter und Überschriften präzise klassifiziert werden.
  - **Unterstreichungstrennung (`textord_restore_underlines=1` & `textord_underline_threshold=0.5`)**: Trennt horizontale Unterstreichungen gezielt von Unterlängen (`g`, `j`, `p`, `q`, `y`).
  - **Sanftes Kanten-Sharpening**: `ImageFilter.UnsharpMask(radius=1.2, percent=115, threshold=3)` vor der Übergabe an Tesseract schärft Kanten für maximale OCR-Präzision.
- **Digi4School Interaktive Seitenauswahl & 2-Thumb Range-Slider**:
  - **Automatische Buch- & Seitenzahlerkennung**: Neue Methode `Digi4SchoolService.inspect_book` loggt sich headless im Hintergrund ein und liest Buchtitel sowie die exakte Gesamtzahl der Buchseiten aus.
  - **Ladedialog `Digi4SchoolDetectModal`**: Kurze Ladeanzeige (*"Connecting to Digi4School and detecting book pages..."*) mit Lade-Spinner und Abbrechen-Möglichkeit.
  - **Menü `Digi4SchoolPageRangeModal`**: Kompaktes Auswahldialog-Layout mit Buchtitel, Zugangscode, 2-Thumb-Slider, synchronisierten Ziffernfeldern und zentriertem *All*-Button.
  - **Interaktives `TwoThumbRangeSlider` Widget**:
    - Stellt eine visuelle Schiene mit 2 Schiebern (Startseite und Endseite) im Catppuccin Mocha-Design dar.
    - Volle Mausbedienung (Klick auf Schiene zur Positionierung des nächstgelegenen Griffs sowie Halten und Ziehen per Drag & Drop).
    - Tastaturnavigation mit Pfeiltasten (`Left`/`Right`, `Shift` für 10er-Schritte, `Tab`/`1`/`2` zum Wechseln des aktiven Schiebers, `Home`/`End`).
  - **Synchronisierte Ziffernfelder**: Zwei Eingabefelder (*"From Page"* und *"To Page"*) zur Direkteingabe; bidirektional in Echtzeit mit dem Schieberegler synchronisiert.
  - **Range-Download & OCR**: Nahtlose Weitergabe des gewählten Seitenbereichs (z. B. `20-50`) an `Digi4SchoolProgressModal` und `Digi4SchoolService.download_book`.
  - 12 neue automatisierte Unit-Tests in `tests/test_page_range_slider.py` (insgesamt 264 Tests in der Gesamtsuite mit 100 % Erfolgsquote).

---

## [1.0.8] - 2026-10-20

### Fixed
- **Main Task Dashboard Formatierung, Sync-Uhrzeit & Spaltenpriorisierung (4K & 1440p Polish)**:
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

## [1.0.7] - 2026-10-20

### Fixed
- **UpdateReminderModal Englisch-Lokalisierung, Button-Layout & Text-Clipping**:
  - **Vollständige englische Lokalisierung**: Alle deutschen Texte, Versionsangaben (`Current Version`, `Latest Version`), Hinweistexte, Fortschrittsmeldungen, Fehlermeldungen und Button-Beschriftungen auf Englisch umgestellt.
  - **2-Zeilen-Button-Layout**: Der `Later [ESC]`-Button wurde unter den beiden Hauptaktionen (`Install Update Now` und `View in Browser`) zentriert platziert, damit kein Button mehr am Dialogrand abgeschnitten wird.
  - **Analoges Error-Buttons-Layout**: Auch bei Downloadfehlern sind die Aktionen nun 2-zeilig aufgeteilt (`Try Again` + `Download in Browser` in Zeile 1, `Close [ESC]` zentriert in Zeile 2).
  - **Hinweistext-Clipping behoben**: `width: 100%` auf `#update_hint` gesetzt für sauberen automatischen Mehrzeilenumbruch, und die Dialogbreite für harmonische Abstände leicht auf `70` Spalten erweitert.
  - **Rich Markup-Absicherung**: `\[ESC]`-Klammern in Button-Labels maskiert, damit Textuals Markup-Parser Tastatur-Shortcuts nicht verschluckt.
  - Neuer automatisierter Test `test_update_reminder_modal_layout_and_english_texts` in `tests/test_update_service.py` (insgesamt 250 Tests in der Gesamtsuite mit 100 % Erfolgsquote).

---

## [1.0.6] - 2026-10-20

### Fixed
- **Main Task Dashboard Vollbreiten-Spaltenverteilung & Beseitigung der horizontalen Scrollleiste**:
  - Dynamische proportionale Breitenberechnung aller 7 Spalten (`#`, `Platform`, `Subject`, `Assignment`, `Due Date`, `Status`, `Teacher`) basierend auf der tatsächlichen Fenster-/Container-Breite analog zum Exams-Screen.
  - Spaltenbreiten werden explizit auf den `DataTable`-Spalten gesetzt (`col.width`, `auto_width = False`), wodurch die Tabelle 100 % der Fensterbreite ausfüllt und horizontaler Überlauf sowie die Scrollleiste vollständig eliminiert werden.
  - Spalte *Assignment* erhält den flexiblen Mittelteil der Breite und wird bei Überschreitung sauber mit `...` (3 ASCII-Punkte) gekürzt (z. B. `OverTheWire/Bandit_0-6_Linux...`).
  - Zeilenumbrüche und überschüssige Whitespaces werden vor der Darstellung bereinigt, um Mehrzeiligkeit oder Formatierungsbrüche zu verhindern.
  - Reagiert sofort auf Terminalgrößenänderungen via `on_resize(term_w_override=...)`.
- **Moodle-Status-Negationsprüfung**:
  - Negationsabsicherung in `Task.is_completed` und `format_status_english`: Texte wie *„Bisher wurden keine Aufgaben abgegeben“* oder *„nicht abgegeben“* werden nicht mehr fälschlicherweise durch das Teilwort *„abgegeben“* als erledigt gewertet, sondern bleiben korrekt als `Open` erhalten.
- 3 neue automatisierte Tests in `tests/test_tui_app.py` (insgesamt 249 Tests in der Gesamtsuite mit 100 % Erfolgsquote).

---

## [1.0.5] - 2026-10-20

### Added
- **Automatische 1-Klick In-App Update-Funktion (`UpdateReminderModal`)**:
  - Direkter Download des offiziellen Release-Installers (`AufgabenDetector_Setup.exe`) innerhalb des Modals mit Textual `ProgressBar`, Byte-/MB- und Prozentanzeige sowie Abbruchmöglichkeit (`cancel_event`).
  - Robuste Fehlerbehandlung mit Retry- und Fallback-Button ("Im Browser herunterladen").
  - **Zielordner- & Konfigurationserhalt**: Installation erfolgt zwingend im aktuellen Programmverzeichnis (`WORKSPACE_DIR`); `config.json`, `data/`, Caches und persönliche Einstellungen bleiben unberührt.
  - **Keine PATH-Modifikation**: Durch Übergabe von `/NOTASKS=1` und `/UPDATE=1` an Inno Setup (`aufgaben_detector.iss`) wird `setup_command.bat` übersprungen und die `PATH`-Variable nicht verändert.
  - **Automatisches Abhängigkeiten-Update**: `setup.bat /silent` prüft und installiert neue pip requirements im Hintergrund ohne blockierende Pause-Abfragen.
  - **Entkoppelter Handoff & Auto-Neustart**: `%TEMP%\AufgabenDetector_Update\apply_update.cmd` wartet auf Beenden des Python-Prozesses, führt die Aktualisierung geräuschlos (`/VERYSILENT`) durch und startet `run.bat` neu.
  - 5 neue Unit- und UI-Tests in `tests/test_update_service.py` (insgesamt 246 Tests in der Gesamtsuite mit 100 % Erfolgsquote).
- **Per-Monitor DPI-Awareness v2 & Native Windows Explorer Dialoge**:
  - Neues Modul `src/core/win_dialogs.py` mit `enable_high_dpi_awareness()`, `pick_file()` und `pick_directory()`.
  - Aktiviert `SetProcessDpiAwarenessContext(HANDLE(-4))` (Per-Monitor DPI Aware v2) direkt beim Start von `main.py`, `src/main.py` und der TUI (`AufgabenApp.on_mount`) sowie vor jedem Dialogaufruf.
  - Echte native Windows COM `IFileOpenDialog`-Instanzen für Dateiauswahl (`/link` in Schulbüchern) und moderne Ordnerauswahl mit `FOS_PICKFOLDERS` (`/link` in Directories) mit nativer Schnellzugriff- und Adressleisten-Navigation.
  - Gestochen scharfe Text-, Icon- und UI-Darstellung auf 4K-, 1440p- und Multi-Monitor-Setups ohne bilineare DWM-Bitmap-Streckung („Low-Res-Explorer-Effekt“).
  - Graceful Fallback Cascade auf DPI-aware Tkinter (`filedialog`) und PowerShell Forms Dialoge bei Nicht-Windows-Systemen oder COM-Ausfällen.
  - 11 neue automatisierte Tests in `tests/test_win_dialogs.py`.

### Fixed
- **SettingsModal Button-Clipping, Abstände & Fensterproportionen**:
  - `ensure_terminal_window_size`: Startbreite auf 123 Spalten und Mindesthöhe dynamisch auf 33 Textzeilen skaliert (`effective_min_h`), angepasst an Windows Terminal und Per-Monitor DPI Awareness v2.
  - `SettingsModal`: Container `#settings_dialog` auf `VerticalScroll` umgestellt, Button-Abstände (`margin-bottom: 1;`, `padding: 1 2;`) exakt an `FilterMenuModal` angeglichen und maximale Höhe auf `96%` erweitert. Der `[↩️ Close [ESC]]`-Button bleibt jederzeit voll sichtbar und erreichbar.
- **ExamsScreen Vollbreiten-Spaltenverteilung & Beseitigung des rechten Leerraums**:
  - Dynamische proportionale Breitenberechnung aller 9 Spalten (`#`, `Type`, `Subject`, `Date`, `Time`, `Topic / Notes`, `Teacher`, `Room`, `Countdown`) basierend auf der tatsächlichen Fenster-/Container-Breite.
  - Spaltenbreiten werden direkt auf den `DataTable`-Spalten gesetzt (`col.width`, `auto_width = False`), wodurch die Tabelle nahtlos bündig bis an den rechten Rand abschließt und der blaue Zeilen-Cursor die gesamte Fensterbreite hervorhebt.
  - Thema / Notizen (`Topic / Notes`) erhält dynamisch bis zu 60 % des zusätzlichen Freiraums (z. B. 60+ Zeichen auf breiten Bildschirmen), wodurch lange Titel und Notizen ohne unnötige Abkürzung dargestellt werden.
  - Berücksichtigt Puffer für vertikale Scrollbars und reagiert sofort auf Fenster-Resize (`on_resize`).
  - Neuer Test `test_exams_screen_full_width_column_distribution_and_resize` in `tests/test_untis_exams.py` (insgesamt 247 bestandene Tests).
- **FilterMenuModal Bereinigung**: Die redundante Textzeile (`#filter_info`) unter dem Titel („Status: ... | Due Window: ...“) wurde entfernt, da die aktiven Filterzustände bereits direkt auf den jeweiligen Farb-Buttons übersichtlich dargestellt werden.
- **Dynamische Datumsabsicherung in `test_untis_exams.py`**: Ersetzung des statischen Testdatums durch relative `timedelta`-Offsets zur Vermeidung von Datumsüberläufen bei zukünftigen Testläufen.

---

## [1.0.4] - 2026-10-19

### Added
- **Directories Tab in Unified CommandPalette**: Neuer 3. Tab in der `Backspace`-Palette (`Courses` ➔ `Schoolbooks` ➔ `Directories` via `Tab`), um Ordner direkt mit nativem Windows-Auswahldialog (`/link`) zu verknüpfen und per `Enter` im Windows Explorer zu öffnen.
- **Headless CLI für Verzeichnisse**: Neue Unterbefehle `tasks dirs [list|open|add|remove] [--json]`.
- **Lokale Verzeichnis-Persistenz**: Speicherung in `data/directories.json` (automatisch via `.gitignore` von Git-Tracking ausgeschlossen).
- **OLED Theme**: Neues Theme `oled` mit reinem Tiefschwarz (`#000000` Background/Surface/Panel) kombiniert mit Flexoki-Farbakzenten.
- **Windows-Tastatur-Shortcuts für Texteingaben**: Umfassende Textbearbeitungs-Shortcuts (`Ctrl+A`, `Pos1`, `Ende`, `Shift+Pos1`, `Shift+Ende`, `Ctrl+Left/Right`, `Shift+Ctrl+Left/Right`, `Ctrl+Delete`, `Ctrl+Backspace`) über alle `Input`- und `TextArea`-Widgets.
- **5-Stufen-Absicherung für `Ctrl+Backspace`**:
  - Stufe 1: ConPTY Win32 Driver Event-Patch für Windows Terminal.
  - Stufe 2: Hardwarenahe OS-Abfrage via `GetAsyncKeyState(VK_CONTROL)` (`0x11`).
  - Stufe 3: Palette-Guard in `UnifiedCommandInput.action_delete_left`.
  - Stufe 4: App-Level Menü-Guard gegen versehentliches Palette-Öffnen.
  - Stufe 5: Fallback Terminal-Bindings (`ctrl+backspace`, `ctrl+w`, `ctrl+h`).
- 19 automatisierte Tests für Verzeichnisse, OLED-Styling und Keyboard-Shortcuts (insgesamt 230 Tests).

### Changed
- **OLED UI Polish**: Rahmen (`border`) von `Header`, `#info_bar` und `#button_bar` im OLED-Theme entfernt, um vertikales Clipping zu verhindern.
- **Button-Höhen normiert**: Feste Höhe von 3 Zeilen (`height: 3`) für alle Dialog- und Modal-Buttons im OLED-Theme für saubere Textzentrierung.
- **Tabellen-Header**: Tabellen-Spaltentitel auf kontrastreiches Weiß (`#ffffff`, bold) umgestellt.
- **Tabellen-Fokus**: Verhindert das Aufhellen des tiefschwarzen Hintergrunds beim Fokussieren (`Tab`) durch Textuals Standard-Fokus-Tint.

### Fixed
- Versehentliches Schließen der `UnifiedCommandPalette` beim Löschen markierter Texte oder beim Drücken von `Ctrl+Backspace`.

---

## [1.0.3] - 2026-10-19

### Added
- **Asynchroner Update-Checker**: Zero-Login GitHub REST API Versionsprüfung mit SemVer-Parser (`src/services/update_service.py`).
- **UpdateReminderModal**: Start-Modal bei neueren Releases mit Anzeige der aktuellen und neuen Version sowie 1-Klick-Download im Browser (`Enter`) und Abbrechen (`ESC`).
- **Versions-Badge in Settings**: Pinned Versions-Badge (`v1.0.3`) in der rechten oberen Ecke des `SettingsModal` (`[O]`).
- **Non-blocking Daemon-Thread**: Update-Prüfung erfolgt im Hintergrund; sofortiger Offline-Start (`< 0.1s`) bleibt vollständig erhalten.
- 9 automatisierte Unit- und UI-Tests in `tests/test_update_service.py` (insgesamt 206 Tests).

---

## [1.0.2] - 2026-10-19

### Added
- **Dependency Pre-flight Checker**: Zero-Dependency Vorabprüfung in `src/core/dependency_checker.py` mit ASCII-Warnbanner und interaktiver Auto-Installation (`[Y/n]`).
- **Theme-Bibliothek auf 21 Themes erweitert**: Gruvbox, Rosé Pine Varianten, Solarized, Catppuccin Varianten, Atom One, Flexoki, ANSI vintage u. v. m.
- **Theme-Favoriten (`⭐`) per Rechtsklick**: Favoriten-Verwaltung in `data/config.json`, Sortierung an den Anfang der Theme-Listen in `ThemeSelectModal` und Command Palette.
