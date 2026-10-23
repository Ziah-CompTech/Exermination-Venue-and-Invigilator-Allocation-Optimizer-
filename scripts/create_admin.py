"""
Create the first administrator account.

Usage:
    python scripts/create_admin.py

Reads ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD from the environment
if set; otherwise prompts interactively.
"""
import os
import sys
from getpass import getpass

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models.user import User


def main():
    app = create_app()
    with app.app_context():
        username = os.environ.get("ADMIN_USERNAME") or input("Admin username: ").strip()
        email = os.environ.get("ADMIN_EMAIL") or input("Admin email: ").strip()
        password = os.environ.get("ADMIN_PASSWORD") or getpass("Admin password: ")

        if User.query.filter_by(username=username).first():
            print(f"User '{username}' already exists.")
            return
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            return

        user = User(username=username, email=email,
                    full_name="System Administrator",
                    role="admin", is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Administrator '{username}' created successfully.")


if __name__ == "__main__":
    main()