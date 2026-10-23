"""Create all database tables. Usage: python scripts/init_db.py"""
import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    db.create_all()
    print("Tables created (or already present).")