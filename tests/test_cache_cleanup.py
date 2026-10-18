"""
test_cache_cleanup.py - Unit-Tests für die sichere Browser-Cache-Bereinigung.
"""

import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import src

from config import (
    clean_browser_profile_caches,
    SAFE_CACHE_SUBDIRS,
    AUTO_CLEAN_BROWSER_CACHE,
    CHROMIUM_CACHE_ARGS,
)


class TestCacheCleanup(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_cache_profile_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_safe_cache_cleaning_preserves_auth(self):
        """Verifiziert, dass temporäre Caches gelöscht werden, aber Cookies & Storage unberührt bleiben."""
        # 1. Temporäre Caches erstellen (sollen gelöscht werden)
        cache_dir = os.path.join(self.test_dir, "Default", "Cache")
        code_cache_dir = os.path.join(self.test_dir, "Default", "Code Cache", "js")
        gpu_cache_dir = os.path.join(self.test_dir, "Default", "GPUCache")
        shader_dir = os.path.join(self.test_dir, "GrShaderCache")

        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(code_cache_dir, exist_ok=True)
        os.makedirs(gpu_cache_dir, exist_ok=True)
        os.makedirs(shader_dir, exist_ok=True)

        with open(os.path.join(cache_dir, "data_0"), "wb") as f:
            f.write(b"X" * 1024)
        with open(os.path.join(code_cache_dir, "script.bin"), "wb") as f:
            f.write(b"Y" * 2048)
        with open(os.path.join(gpu_cache_dir, "data_0"), "wb") as f:
            f.write(b"G" * 512)
        with open(os.path.join(shader_dir, "shader.bin"), "wb") as f:
            f.write(b"S" * 512)

        # 2. Kritische Auth- und Persistenzdaten erstellen (müssen erhalten bleiben!)
        network_dir = os.path.join(self.test_dir, "Default", "Network")
        local_storage_dir = os.path.join(self.test_dir, "Default", "Local Storage", "leveldb")
        indexed_db_dir = os.path.join(self.test_dir, "Default", "IndexedDB", "teams_db")
        sw_dir = os.path.join(self.test_dir, "Default", "Service Worker", "CacheStorage")

        os.makedirs(network_dir, exist_ok=True)
        os.makedirs(local_storage_dir, exist_ok=True)
        os.makedirs(indexed_db_dir, exist_ok=True)
        os.makedirs(sw_dir, exist_ok=True)

        cookies_file = os.path.join(network_dir, "Cookies")
        with open(cookies_file, "wb") as f:
            f.write(b"COOKIE_SESSION_DATA_SQLITE")

        storage_file = os.path.join(local_storage_dir, "000001.log")
        with open(storage_file, "wb") as f:
            f.write(b"MSAL_AUTH_TOKENS")

        db_file = os.path.join(indexed_db_dir, "data.ldb")
        with open(db_file, "wb") as f:
            f.write(b"INDEXED_DB_DATA")

        sw_file = os.path.join(sw_dir, "index.txt")
        with open(sw_file, "wb") as f:
            f.write(b"SW_REGISTRATION_DATA")

        # 3. Bereinigung ausführen (threshold_mb=0 um immer auszulösen)
        freed = clean_browser_profile_caches([self.test_dir], threshold_mb=0)

        # 4. Überprüfen: Freigegebener Speicher
        expected_min = 1024 + 2048 + 512 + 512
        self.assertGreaterEqual(freed, expected_min)

        # 5. Überprüfen: Temporäre Cache-Ordner sind entfernt
        self.assertFalse(os.path.exists(cache_dir))
        self.assertFalse(os.path.exists(code_cache_dir))
        self.assertFalse(os.path.exists(gpu_cache_dir))
        self.assertFalse(os.path.exists(shader_dir))

        # 6. Überprüfen: Auth-Dateien existieren weiterhin unversehrt!
        self.assertTrue(os.path.exists(cookies_file))
        with open(cookies_file, "rb") as f:
            self.assertEqual(f.read(), b"COOKIE_SESSION_DATA_SQLITE")

        self.assertTrue(os.path.exists(storage_file))
        with open(storage_file, "rb") as f:
            self.assertEqual(f.read(), b"MSAL_AUTH_TOKENS")

        self.assertTrue(os.path.exists(db_file))
        self.assertTrue(os.path.exists(sw_file))

    def test_nonexistent_profile_handled_gracefully(self):
        """Prüft, dass nicht existierende Pfade ohne Fehler ignoriert werden."""
        dummy_path = os.path.join(self.test_dir, "does_not_exist")
        freed = clean_browser_profile_caches([dummy_path])
        self.assertEqual(freed, 0)

    def test_chromium_cache_args_configured(self):
        """Stellt sicher, dass das Cache-Limit-Flag definiert ist."""
        self.assertTrue(any("--disk-cache-size=" in arg for arg in CHROMIUM_CACHE_ARGS))


if __name__ == "__main__":
    unittest.main()
