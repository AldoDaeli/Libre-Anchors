import importlib
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class VercelPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["INSTANCE_DIR"] = tempfile.mkdtemp()
        os.environ["APP_ENV"] = "development"
        os.environ["MAIL_BACKEND"] = "memory"
        os.environ.pop("DATABASE_URL", None)
        mod = importlib.import_module("api.index")
        cls.c = mod.app.test_client()

    def test_root_restored(self):
        r = self.c.get("/api/index?__p=")
        self.assertEqual(r.status_code, 200)   # beranda dilayani langsung di "/"

    def test_static_page_served(self):
        r = self.c.get("/api/index?__p=login")
        self.assertEqual(r.status_code, 200)
        r = self.c.get("/api/index?__p=landing.css")
        self.assertEqual(r.status_code, 200)

    def test_api_path_restored(self):
        r = self.c.get("/api/index?__p=api/csrf")
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.get_json())

    def test_original_query_preserved(self):
        r = self.c.get("/api/index?__p=distro.html&d=ubuntu")  # URL lama -> URL bersih
        self.assertEqual(r.headers["Location"], "/distro/ubuntu")
        r = self.c.get("/api/index?__p=distro/ubuntu")          # tamu -> /login
        self.assertEqual(r.headers["Location"], "/login")

    def test_traversal_blocked(self):
        for p in ("../app.py", "..%2F..%2Fetc%2Fpasswd", ".env", "static/../.env"):
            self.assertEqual(self.c.get("/api/index?__p=" + p).status_code, 404, p)


if __name__ == "__main__":
    unittest.main()