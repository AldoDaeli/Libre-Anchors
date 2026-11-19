"""Titik masuk Vercel (Python serverless function).

Pemulihan alamat asli (query "__p" -> PATH_INFO) dilakukan di app.create_app() lewat RestorePath,
jadi file entrypoint mana pun yang dipilih Vercel (app.py / wsgi.py / api/index.py) berperilaku sama.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402

app = create_app()