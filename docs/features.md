# Feature & UI Element Catalog — Aufgaben-Detector

> **Zweck**: Eindeutige, token-effiziente Begriffswelt für Buttons, UI-Elemente und Features zwischen Benutzer und Agent.  
> **Regel**: Maximal 1 prägnanter Satz pro Eintrag. Exakte Bezeichnungen gemäß TUI- und CLI-Codebase.

---

## 1. Screens & Hauptansichten

| Element / View | Typ | Kurzbeschreibung |
| :--- | :--- | :--- |
| `Main Task Dashboard` | Screen | Farbcodierte Haupttabelle aller offenen und fälligen Moodle- und Teams-Aufgaben (`AufgabenDetectorApp`). |
| `Tests & Exams Screen` (`[E]`) | Screen | WebUntis Prüfungskalender mit Datums-, Raum- und Fachangaben sowie Prüfungstyp (`ExamsScreen`). |
| `CommandPalette` (`Backspace` / `/`) | Overlay | Schnellsuchleiste mit `Tab`-Umschaltung zwischen *Courses* (Moodle-Links) und *Schoolbooks*. |
| `Trash / Hidden Screen` (`[G]`) | Modal | Übersicht aller ausgeblendeten oder gelöschten Aufgaben mit Wiederherstellungsoption (`TrashModal`). |

---

## 2. Modals & Dialoge

| Dialog / Modal | Typ | Kurzbeschreibung |
| :--- | :--- | :--- |
| `TaskDetailModal` | Modal | Zeigt formatierte Angabe (`angabe.md`), Metadaten und Aktions-Buttons für eine gewählte Aufgabe. |
| `AddTaskModal` (`[A]`) | Modal | Eingabemaske zur manuellen Erstellung eigener Hausübungen oder Notizen mit Fälligkeitsdatum. |
| `FilterMenuModal` (`[F]`) | Modal | Filter-Dialog für Status (Offen/Überfällig/Erledigt), Fach und Zeitfenster (`FilterMenuModal`). |
| `SubjectFilterModal` | Modal | Listen-Auswahl zur Einschränkung der Tabelle auf ein spezifisches Schulfach. |
| `ExcuseLetterModal` (`[U]`) | Modal | Fehlstunden-Übersicht mit Stundenplan-Abgleich und 1-Klick-PDF-Export für die Schule. |
| `ExamDetailModal` | Modal | Zeigt Prüfungsdetails und ermöglicht das Bearbeiten persönlicher Stoff-Notizen (`exam_notes.json`). |
| `AddExamModal` | Modal | Formular zum Eintragen manueller Prüfungstermine mit nativer Wochentagserkennung. |
| `SettingsModal` (`[O]`) | Modal | Konfigurationsdialog für Schülerprofil, Lehrer, Schule, Untis-Gruppe und Farbthema. |
| `LoginChoiceModal` (`[L]`) | Modal | Zentrales Auswahlmenü für Anmeldungen bei Moodle, Microsoft Teams und WebUntis. |
| `TeamsSetupModal` | Modal | Geführter Teams-Login via Playwright-Chromium mit Passkey-, 2FA- oder Kennwort-Unterstützung. |
| `MoodleLoginModal` | Modal | Eingabe von Moodle-Benutzername und Passwort mit automatischer Session-Cookie-Speicherung. |
| `UntisSetupModal` | Modal | Konfiguration von WebUntis-Schulname, Benutzer und Passwort. |
| `GitSetupModal` | Modal | Einrichtungsdialog für cloudbasierten Git-Sync über privates Repository mit Token-Verschleierung. |
| `SchoolbookUrlModal` | Modal | Dialog zur Vergabe von Buchtitel und Web-URL für digitale Schulbücher. |
| `Digi4SchoolDownloadModal` | Modal | Anmelde- und Zugangscode-Eingabe für den automatischen Digi4School-Buchdownload. |
| `Digi4SchoolProgressModal` | Modal | Fortschrittsanzeige mit Multi-Core OCR-Status, verbleibender Zeit (ETA) und Abbruch-Option. |

---

## 3. Buttons & Interaktions-Elemente

| Button / Control | ID / Key | Kurzbeschreibung |
| :--- | :--- | :--- |
| `Open in browser` | `[O]` / `btn_open_browser` | Öffnet die offizielle Abgabeseite der Aufgabe direkt im Standard-Webbrowser. |
| `Download files` | `[D]` / `btn_download_files` | Lädt alle Anhänge und die Angabe in `%USERPROFILE%\Downloads\<Fach> - <Titel>\` und öffnet den Explorer. |
| `Toggle status` | `[E]` / `btn_toggle_status` | Schaltet den Erledigt-Status einer Aufgabe zwischen offen und abgeschlossen um. |
| `Hide / Delete` | `[L]` / `btn_delete_task` | Verschiebt eine Aufgabe in den lokalen Papierkorb (`deleted_tasks.json`). |
| `Restore` | `[W]` / `btn_restore_task` | Stellt eine gelöschte Aufgabe aus dem Papierkorb wieder her. |
| `Generate Excuse PDF` | `btn_generate_excuse` | Erzeugt das druckfertige Entschuldigungsschreiben als PDF und öffnet den System-Betrachter. |
| `Synchronize` | `[R]` / `btn_sync` | Startet den sofortigen Hintergrund-Abgleich mit Moodle, Teams und WebUntis. |
| `Change Theme` | `[T]` / `Ctrl+P` | Rotiert durch die integrierten Farbthemen (Catppuccin Mocha, Nord, Dracula, Monokai). |
| `Restore all` | `[W]` / `btn_trash_restore_all` | Stellt sämtliche ausgeblendeten Aufgaben auf einen Schlag wieder her. |

---

## 4. CommandPalette Befehle (Schulbücher & Kurse)

| Befehl / Syntax | Modus | Kurzbeschreibung |
| :--- | :--- | :--- |
| `<Suchbegriff>` | Courses (Cyan) | Filtert Moodle-Kurse nach Fach oder Name und öffnet den gewählten Kurs im Browser. |
| `<Suchbegriff>` | Books (Rot) | Durchsucht die verknüpfte Schulbuch-Bibliothek und öffnet das gewählte Buch (PDF oder Web). |
| `/link` | Books | Öffnet den nativen Windows-Dateidialog zum Verknüpfen einer lokalen Schulbuch-PDF. |
| `/url <URL>` | Books | Öffnet den Eingabedialog zum Hinterlegen eines webbasierten Schulbuchs. |
| `/download <Code>` | Books | Startet den Digi4School Grabber und erzeugt ein durchsuchbares OCR-Sandwich-PDF. |
| `/unlink` | Books | Entfernt ein verknüpftes Buch aus der lokalen Liste (`data/schoolbooks.json`). |

---

## 5. Headless Agent CLI Befehle (`tasks`)

| CLI Befehl | Optionen / Flags | Kurzbeschreibung |
| :--- | :--- | :--- |
| `tasks list` | `-s <status> -f <fach> --json` | Listet Aufgaben tabellarisch oder als JSON für KI-Agenten auf. |
| `tasks show <id>` | `--json` | Gibt vollständige Metadaten und Aufgabenstellung einer Aufgabe im Terminal aus. |
| `tasks download <id>` | `--dir <pfad>` | Lädt Anhänge und Angabe headless in das Zielverzeichnis herunter. |
| `tasks open <fach>` | — | Öffnet den Moodle-Kurs des angegebenen Fachs im Standard-Webbrowser. |
| `tasks books list` | `--json` | Gibt alle verknüpften Schulbücher aus. |
| `tasks books open <id>` | — | Startet das angegebene Schulbuch im OS-Standardviewer oder Webbrowser. |
| `tasks books add <pfad>` | `--title <titel>` | Verknüpft eine lokale PDF-Datei oder Web-URL headless als Schulbuch. |
| `tasks books download <code>` | `--email <m> --password <p>` | Lädt ein Digi4School-Buch im Terminal herunter und generiert das OCR-PDF. |
| `tasks sync` | `--deep` | Führt eine vollständige Plattform-Synchronisation im Hintergrund durch. |
