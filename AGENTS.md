# AGENTS.md — Aufgaben-Detector Master Index & Guidelines

> **Project**: Aufgaben-Detector (Moodle, Microsoft Teams & WebUntis)  
> **Tech Stack**: Python 3.10+, Textual, Playwright, Requests, ReportLab / PyMuPDF  
> **Documentation Root**: `docs/`

---

## 1. Quick Reference & Commands

- **Run TUI (Interactive)**: `python main.py` or `.\run.bat`
- **Run CLI (Agent / Headless)**: `.\tasks.bat <cmd>` or `python main.py <cmd>`
  - List tasks: `tasks list [-s all|open|overdue|completed] [-f <fach>] [-p moodle|teams] [--json]`
  - Task details: `tasks show <id|index> [--json]`
  - Download attachments: `tasks download <id|index> [--dir <path>]`
  - Open course in browser: `tasks open <fach>`
  - Schoolbooks (PDF / Web / Digi4School): `tasks books [list|open|add|remove|download] [--json]`
  - Sync platforms: `tasks sync [--deep]`
- **Tests**: `python -m unittest discover tests` or `pytest tests/`
- **Setup & Dependencies**: `.\setup.bat`

---

## 2. Documentation Matrix (Progressive Disclosure)

> [!IMPORTANT]
> **Do not load all doc files at once!** Consult this matrix and read ONLY the file relevant to your immediate task via `view_file`.

| Document | Purpose / Topics Covered | When to Read (Trigger Condition) |
| :--- | :--- | :--- |
| [`docs/current-state.md`](docs/current-state.md) | **Session Handoff**, active milestone, completed features, next steps | **Every session start** or when asked about status/progress |
| [`docs/project-overview.md`](docs/project-overview.md) | Purpose, target audience, core features (Moodle, Teams, Untis, Downloads), scope | When starting major features or clarifying domain logic |
| [`docs/architecture.md`](docs/architecture.md) | Components (`src/core`, `services`, `ui`), data flows, caching (`<0.1s`), data models | When modifying system modules, APIs, caching, or data models |
| [`docs/conventions.md`](docs/conventions.md) | Code style, zero-knowledge rules, CLI token-efficiency, test guidelines | When writing code, adding CLI commands, or refactoring |
| [`docs/decisions.md`](docs/decisions.md) | Architecture Decision Records (ADRs: Playwright, Textual, Untis JSON-RPC, Licensing) | Before altering architectural patterns or tech choices |

---

## 3. Agent Protocol & Memory Maintenance

1. **Start of Task**: Consult [`docs/current-state.md`](docs/current-state.md) to pick up with zero knowledge loss.
2. **During Task**: Strictly follow rules in [`docs/conventions.md`](docs/conventions.md) and respect [`docs/decisions.md`](docs/decisions.md).
3. **End of Task / Session Handoff**:
   - Update [`docs/current-state.md`](docs/current-state.md) (mark finished items `[x]`, list next steps `[ ]`).
   - If architecture, APIs, or conventions change, update the corresponding `docs/*.md` file.
   - Keep this `AGENTS.md` lean (< 3 KB).
