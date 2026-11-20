"""Titik masuk production:  gunicorn -w 3 -b 127.0.0.1:8000 wsgi:app"""
from app import app  # noqa: F401