import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("INSTANCE_DIR", tempfile.mkdtemp())
os.environ["MAIL_BACKEND"] = "memory"
os.environ.pop("DATABASE_URL", None)


class EntrypointTests(unittest.TestCase):
    """Vercel mencari variabel Flask bernama `app` di app.py / wsgi.py."""

    def test_app_variable_exposed(self):
        from flask import Flask
        import app as module
        import wsgi
        self.assertIsInstance(module.app, Flask)
        self.assertIs(wsgi.app, module.app)

    def test_pages_served_with_original_paths(self):
        import app as module
        c = module.app.test_client()
        for path in ("/", "/login", "/register", "/landing.css", "/favicon.ico"):
            self.assertEqual(c.get(path).status_code, 200, path)
        self.assertEqual(c.get("/profil").headers["Location"], "/login")


if __name__ == "__main__":
    unittest.main()