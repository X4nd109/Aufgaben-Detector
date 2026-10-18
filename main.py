"""
main.py - Zentraler Einstiegspunkt für den Aufgaben-Detector.
Startet das moderne TUI oder den CLI-Modus aus dem src/-Paket.
"""
import os
import sys

# Projekt-Root und Quellverzeichnisse im PYTHONPATH registrieren
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_ROOT_DIR, "src")
for _sub in [_ROOT_DIR, _SRC_DIR, os.path.join(_SRC_DIR, "core"), os.path.join(_SRC_DIR, "services"), os.path.join(_SRC_DIR, "ui")]:
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

from src.main import main

if __name__ == "__main__":
    main()
