"""
tests package initialization - stellt sicher, dass src und alle Submodule importiert werden können.
"""
import os
import sys

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_TEST_DIR)
_SRC_DIR = os.path.join(_ROOT_DIR, "src")

for _sub in [_ROOT_DIR, _SRC_DIR, os.path.join(_SRC_DIR, "core"), os.path.join(_SRC_DIR, "services"), os.path.join(_SRC_DIR, "ui")]:
    if _sub not in sys.path:
        sys.path.insert(0, _sub)
