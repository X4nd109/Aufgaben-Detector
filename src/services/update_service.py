"""
update_service.py - Asynchroner Versions- und Update-Checker für GitHub Releases.
"""

import json
import logging
import re
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Tuple

from src.core.config import APP_VERSION, GITHUB_REPO

logger = logging.getLogger(__name__)


def parse_version(v_str: str) -> Tuple[int, ...]:
    """
    Parst einen Versions-String (z. B. 'v1.0.2', '1.0.3-beta', '2.0')
    in ein Tupel ganzer Zahlen zur zuverlässigen semantischen Versionsprüfung.
    """
    if not v_str:
        return (0,)
    # Entferne eventuelle führende Präfixe wie 'v' oder 'release-'
    cleaned = v_str.strip().lstrip("vV")
    numbers = re.findall(r"\d+", cleaned)
    if not numbers:
        return (0,)
    return tuple(int(n) for n in numbers)


def is_newer_version(latest_tag: str, current_version: str = APP_VERSION) -> bool:
    """
    Gibt True zurück, wenn latest_tag semantisch höher als current_version ist.
    Gleicht bei unterschiedlichen Längen (z. B. 1.0 vs 1.0.2) die Tupel mit Nullen an.
    """
    v_latest = list(parse_version(latest_tag))
    v_current = list(parse_version(current_version))

    max_len = max(len(v_latest), len(v_current))
    while len(v_latest) < max_len:
        v_latest.append(0)
    while len(v_current) < max_len:
        v_current.append(0)

    return tuple(v_latest) > tuple(v_current)


def check_for_updates(
    current_version: str = APP_VERSION,
    repo: str = GITHUB_REPO,
    timeout: float = 3.0,
) -> Optional[Dict[str, Any]]:
    """
    Prüft geräuschlos über die GitHub REST-API, ob ein neuer Release vorliegt.
    
    Gibt bei einem neueren Release ein Dict mit Details zurück,
    andernfalls (keine neuere Version, Offline, Timeout, Rate-Limit) None.
    """
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": f"Aufgaben-Detector/{current_version}",
            "Accept": "application/vnd.github.v3+json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return None
            data = json.loads(response.read().decode("utf-8"))

        tag_name = data.get("tag_name", "").strip()
        if not tag_name:
            return None

        if is_newer_version(tag_name, current_version):
            clean_latest = tag_name.lstrip("vV")
            return {
                "current_version": current_version.lstrip("vV"),
                "latest_version": clean_latest,
                "tag_name": tag_name,
                "name": data.get("name") or tag_name,
                "html_url": data.get("html_url") or f"https://github.com/{repo}/releases/latest",
                "body": (data.get("body") or "").strip(),
                "published_at": data.get("published_at") or "",
            }

        return None

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        # Geräuschloses Abfangen bei Offline-Betrieb oder Netzwerkausfällen
        return None
    except Exception as e:
        logger.debug("Unerwarteter Fehler bei Update-Prüfung: %s", e)
        return None
