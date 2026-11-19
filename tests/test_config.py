import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_config  # noqa: E402
from db import _pg_url  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_vercel_requires_database_url(self):
        with self.assertRaises(RuntimeError) as cm:
            load_config({"ON_VERCEL": True, "DATABASE_URL": ""})
        self.assertIn("DATABASE_URL", str(cm.exception))

    def test_database_url_must_be_postgres(self):
        with self.assertRaises(RuntimeError):
            load_config({"DATABASE_URL": "mysql://x"})

    def test_tls_forced_for_postgres(self):
        self.assertTrue(_pg_url("postgresql://u:p@h:6543/postgres").endswith("?sslmode=require"))
        self.assertTrue(_pg_url("postgresql://u:p@h/db?x=1").endswith("&sslmode=require"))
        self.assertEqual(_pg_url("postgresql://u:p@h/db?sslmode=verify-full"), "postgresql://u:p@h/db?sslmode=verify-full")


if __name__ == "__main__":
    unittest.main()
