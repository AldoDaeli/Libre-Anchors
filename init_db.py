"""Buat tabel di Supabase:  DATABASE_URL=... python init_db.py
(Atau tempel isi schema_postgres.sql di Supabase > SQL Editor.)"""
from app import create_app
import db as database

app = create_app({"AUTO_INIT_DB": True})
with app.app_context():
    database.init_db()
    print("Skema siap.")
