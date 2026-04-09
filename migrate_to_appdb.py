#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
One-time migration:
- baza.db:tabela(epoch, humidity, pressure, temp_hum, temp_prs) -> app.db:sensor_readings
- login.db:user (SQLAlchemy default) -> app.db:user (same model)

Safe to re-run: it will only append missing rows based on epoch uniqueness heuristic.
"""

import os
import sqlite3


def _sqlite_path(root: str, name: str) -> str:
    return os.path.join(root, name)


def migrate_readings(repo_root: str) -> int:
    old_path = _sqlite_path(repo_root, "baza.db")
    new_path = _sqlite_path(repo_root, "app.db")

    if not os.path.isfile(old_path):
        print(f"[migrate] skip readings: no {old_path}")
        return 0

    old = sqlite3.connect(old_path)
    old.row_factory = sqlite3.Row
    new = sqlite3.connect(new_path)
    new.row_factory = sqlite3.Row

    with new:
        new.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_readings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              epoch INTEGER NOT NULL,
              humidity REAL,
              pressure REAL,
              temp_hum REAL,
              temp_prs REAL
            )
            """
        )
        new.execute("CREATE INDEX IF NOT EXISTS ix_sensor_readings_epoch ON sensor_readings(epoch)")

    # Find existing epochs to avoid duplicates (cheap heuristic).
    existing = set()
    cur = new.execute("SELECT epoch FROM sensor_readings")
    for row in cur.fetchall():
        existing.add(int(row["epoch"]))

    cur = old.execute("SELECT epoch, humidity, pressure, temp_hum, temp_prs FROM tabela ORDER BY epoch ASC")
    rows = cur.fetchall()
    inserted = 0
    with new:
        for r in rows:
            epoch = int(r["epoch"])
            if epoch in existing:
                continue
            new.execute(
                "INSERT INTO sensor_readings(epoch, humidity, pressure, temp_hum, temp_prs) VALUES(?,?,?,?,?)",
                (
                    epoch,
                    r["humidity"],
                    r["pressure"],
                    r["temp_hum"],
                    r["temp_prs"],
                ),
            )
            inserted += 1

    print(f"[migrate] readings inserted: {inserted} -> {new_path}")
    return inserted


def migrate_users(repo_root: str) -> int:
    old_path = _sqlite_path(repo_root, "login.db")
    new_path = _sqlite_path(repo_root, "app.db")

    if not os.path.isfile(old_path):
        print(f"[migrate] skip users: no {old_path}")
        return 0

    old = sqlite3.connect(old_path)
    old.row_factory = sqlite3.Row
    new = sqlite3.connect(new_path)
    new.row_factory = sqlite3.Row

    # Default SQLAlchemy table name for User model is `user`.
    with new:
        new.execute(
            """
            CREATE TABLE IF NOT EXISTS user (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username VARCHAR(15) UNIQUE,
              email VARCHAR(50) UNIQUE,
              password VARCHAR(80)
            )
            """
        )

    # Copy only missing by username/email.
    existing = set()
    cur = new.execute("SELECT username, email FROM user")
    for r in cur.fetchall():
        existing.add((r["username"], r["email"]))

    try:
        cur = old.execute("SELECT id, username, email, password FROM user")
    except sqlite3.OperationalError:
        print("[migrate] skip users: table `user` not found in login.db")
        return 0

    rows = cur.fetchall()
    inserted = 0
    with new:
        for r in rows:
            key = (r["username"], r["email"])
            if key in existing:
                continue
            new.execute(
                "INSERT INTO user(username, email, password) VALUES(?,?,?)",
                (r["username"], r["email"], r["password"]),
            )
            inserted += 1

    print(f"[migrate] users inserted: {inserted} -> {new_path}")
    return inserted


def main() -> None:
    repo_root = os.path.dirname(os.path.abspath(__file__))
    migrate_readings(repo_root)
    migrate_users(repo_root)


if __name__ == "__main__":  # pragma: no cover
    main()

