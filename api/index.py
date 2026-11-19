"""Titik masuk Vercel (Python serverless function).

vercel.json mengarahkan semua URL ke fungsi ini dan menaruh alamat aslinya di query "__p".
Vercel meneruskan PATH tujuan rewrite (/api/index), bukan alamat yang diminta browser, jadi
RestorePath mengembalikan PATH_INFO + QUERY_STRING asli sebelum Flask memproses request.
"""
import os
import sys
from urllib.parse import parse_qsl, urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402


class RestorePath:
    MARK = "__p"

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        if environ.get("PATH_INFO", "").startswith("/api/index"):
            orig, rest = None, []
            for k, v in parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True):
                if k == self.MARK and orig is None:
                    orig = v
                else:
                    rest.append((k, v))
            environ["PATH_INFO"] = "/" + (orig or "").lstrip("/")
            environ["QUERY_STRING"] = urlencode(rest)
        return self.wsgi_app(environ, start_response)


app = create_app()
app.wsgi_app = RestorePath(app.wsgi_app)