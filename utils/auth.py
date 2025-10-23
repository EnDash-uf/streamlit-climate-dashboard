"""Utility helpers for authentication and user management.

This module wraps all file access to the lightweight JSON user database
so the Streamlit app can stay focused on UI code.  The helpers here keep
all file paths in one place and provide small, well-tested building
blocks for creating, updating, and validating users.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

import bcrypt


# ---------------------------------------------------------------------------
# File locations
# ---------------------------------------------------------------------------
BASE_DIR = Path("data")
USER_DB_PATH = BASE_DIR / "user_db.json"
USER_FILES_DIR = BASE_DIR / "user_files"


def _default_db() -> Dict[str, Any]:
    """Return an empty database structure.

    A helper is used instead of a constant so that tests can easily create a
    clean in-memory copy of the database.
    """

    return {"users": {}}


def load_user_db() -> Dict[str, Any]:
    """Load the user database from disk, creating it if necessary."""

    if not USER_DB_PATH.exists():
        USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        save_user_db(_default_db())
    with USER_DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_user_db(db: Dict[str, Any]) -> None:
    """Persist the supplied database to disk."""

    USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_DB_PATH.open("w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, sort_keys=True)


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash for the provided password."""

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check whether ``plain_password`` matches ``hashed_password``."""

    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        # In case a malformed hash is stored we fail closed.
        return False


def ensure_user_record(db: Dict[str, Any], username: str) -> Dict[str, Any]:
    """Ensure a user record exists and return it."""

    users = db.setdefault("users", {})
    return users.setdefault(
        username,
        {
            "name": username,
            "password_hash": hash_password("changeme"),
            "role": "user",
            "settings": default_settings(),
        },
    )


def default_settings() -> Dict[str, Any]:
    """Provide sensible default user settings."""

    return {
        "unit_preference": "metric",
        "ideal_setpoints": {
            "temperature": 22,
            "humidity": 55,
            "vpd": 0.8,
        },
    }


def create_user(
    username: str,
    name: str,
    password: str,
    role: str = "user",
    settings: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Create a new user entry and persist it."""

    db = load_user_db()
    users = db.setdefault("users", {})
    if username in users:
        raise ValueError(f"User '{username}' already exists")

    users[username] = {
        "name": name,
        "password_hash": hash_password(password),
        "role": role,
        "settings": settings or default_settings(),
    }
    save_user_db(db)
    return users[username]


def update_user_settings(username: str, new_settings: Dict[str, Any]) -> None:
    """Replace the stored settings for ``username`` with ``new_settings``."""

    db = load_user_db()
    user = db.get("users", {}).get(username)
    if not user:
        raise KeyError(f"Unknown user '{username}'")
    user["settings"] = new_settings
    save_user_db(db)


def reset_password(username: str, new_password: str) -> None:
    """Update a user's password to ``new_password``."""

    db = load_user_db()
    user = db.get("users", {}).get(username)
    if not user:
        raise KeyError(f"Unknown user '{username}'")
    user["password_hash"] = hash_password(new_password)
    save_user_db(db)


def delete_user(username: str) -> None:
    """Remove a user and any stored files."""

    db = load_user_db()
    users = db.get("users", {})
    if username in users:
        users.pop(username)
        save_user_db(db)
    # Remove user files so the admin can reclaim storage.
    user_dir = USER_FILES_DIR / safe_username(username)
    if user_dir.exists():
        all_children = sorted(
            user_dir.glob("**/*"), key=lambda p: len(p.parts), reverse=True
        )
        for child in all_children:
            if child.is_file():
                child.unlink(missing_ok=True)
        for child in all_children:
            if child.is_dir():
                child.rmdir()
        user_dir.rmdir()


def list_users() -> Iterable[Dict[str, Any]]:
    """Return an iterable of user records (including usernames)."""

    db = load_user_db()
    for username, data in db.get("users", {}).items():
        yield {
            "username": username,
            "name": data.get("name", username),
            "role": data.get("role", "user"),
            "settings": data.get("settings", default_settings()),
        }


def get_user(username: str) -> Dict[str, Any] | None:
    """Return a user dictionary if it exists."""

    db = load_user_db()
    return db.get("users", {}).get(username)


def safe_username(username: str) -> str:
    """Convert a username into a filesystem-safe directory name."""

    return "_".join(username.split())


def get_user_dir(username: str) -> Path:
    """Return the per-user storage directory, creating it if needed."""

    USER_FILES_DIR.mkdir(parents=True, exist_ok=True)
    user_dir = USER_FILES_DIR / safe_username(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def ensure_admin_exists() -> None:
    """Create a default admin if none exists.

    The repository ships with an admin user, but this helper keeps the app
    resilient in case the JSON file is deleted.
    """

    db = load_user_db()
    users = db.setdefault("users", {})
    if not any(user.get("role") == "admin" for user in users.values()):
        users["admin"] = {
            "name": "Administrator",
            "password_hash": hash_password("Admin123!"),
            "role": "admin",
            "settings": default_settings(),
        }
        save_user_db(db)

