"""Titik masuk Vercel (Python serverless function).

vercel.json mengarahkan semua URL ke fungsi ini dan menaruh alamat aslinya di query "__p".
Vercel meneruskan PATH tujuan rewrite (/api/index), bukan alamat yang diminta browser, jadi
RestorePath mengembalikan PATH_INFO + QUERY_STRING asli sebelum Flask memproses request.
"""
import json
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
        # DIAGNOSTIK SEMENTARA: tampilkan apa yang diterima fungsi (hanya nama jalur & header routing, tanpa cookie/body).
        if os.getenv("ROUTE_DEBUG") == "1":
            info = {
                "method": environ.get("REQUEST_METHOD"),
                "PATH_INFO": environ.get("PATH_INFO"),
                "QUERY_STRING": environ.get("QUERY_STRING"),
                "REQUEST_URI": environ.get("REQUEST_URI") or environ.get("RAW_URI"),
                "SCRIPT_NAME": environ.get("SCRIPT_NAME"),
                "headers": {k: v for k, v in environ.items()
                            if k.startswith(("HTTP_X_VERCEL", "HTTP_X_MATCHED", "HTTP_X_FORWARDED_HOST",
                                             "HTTP_X_FORWARDED_PROTO", "HTTP_X_FORWARDED_URI", "HTTP_X_ORIGINAL"))},
            }
            print("ROUTE_DEBUG " + json.dumps(info), flush=True)
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