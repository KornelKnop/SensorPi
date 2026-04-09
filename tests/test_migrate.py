import sqlite3

import migrate_to_appdb
from migrate_to_appdb import migrate_readings, migrate_users


def test_main_invokes_both_migrations(monkeypatch):
    calls = []

    def track_r(root):
        calls.append("r")

    def track_u(root):
        calls.append("u")

    monkeypatch.setattr(migrate_to_appdb, "migrate_readings", track_r)
    monkeypatch.setattr(migrate_to_appdb, "migrate_users", track_u)
    migrate_to_appdb.main()
    assert calls == ["r", "u"]


def test_migrate_readings_idempotent_second_run_inserts_zero(tmp_path):
    repo = tmp_path / "repo2"
    repo.mkdir()
    old_db = repo / "baza.db"
    con_old = sqlite3.connect(old_db)
    con_old.execute(
        """CREATE TABLE tabela (
            epoch INT, humidity REAL, pressure REAL,
            temp_hum REAL, temp_prs REAL
        )"""
    )
    con_old.execute("INSERT INTO tabela VALUES (2000, 1, 2, 3, 4)")
    con_old.commit()
    con_old.close()
    (repo / "app.db").write_bytes(b"")
    assert migrate_readings(str(repo)) == 1
    assert migrate_readings(str(repo)) == 0


def test_migrate_readings_inserts_rows(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    old_db = repo / "baza.db"
    con_old = sqlite3.connect(old_db)
    con_old.execute(
        """CREATE TABLE tabela (
            epoch INT, humidity REAL, pressure REAL,
            temp_hum REAL, temp_prs REAL
        )"""
    )
    con_old.execute(
        "INSERT INTO tabela VALUES (1000, 50.0, 1000.0, 20.0, 19.0)"
    )
    con_old.commit()
    con_old.close()

    new_db = repo / "app.db"
    new_db.write_bytes(b"")

    n = migrate_readings(str(repo))
    assert n == 1

    con_new = sqlite3.connect(new_db)
    rows = con_new.execute("SELECT epoch, humidity FROM sensor_readings").fetchall()
    con_new.close()
    assert len(rows) == 1
    assert rows[0][0] == 1000
    assert rows[0][1] == 50.0


def test_migrate_readings_skips_when_no_baza(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    assert migrate_readings(str(repo)) == 0


def test_migrate_users_inserts(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()

    login = repo / "login.db"
    c = sqlite3.connect(login)
    c.execute(
        """CREATE TABLE user (
            id INTEGER PRIMARY KEY,
            username VARCHAR(15) UNIQUE,
            email VARCHAR(50) UNIQUE,
            password VARCHAR(80)
        )"""
    )
    c.execute(
        "INSERT INTO user(username, email, password) VALUES (?,?,?)",
        ("u1", "e1@test.com", "hash"),
    )
    c.commit()
    c.close()

    (repo / "app.db").write_bytes(b"")

    n = migrate_users(str(repo))
    assert n == 1

    con = sqlite3.connect(repo / "app.db")
    rows = con.execute("SELECT username FROM user").fetchall()
    con.close()
    assert rows == [("u1",)]


def test_migrate_users_skips_when_no_login_db(tmp_path):
    repo = tmp_path / "no_login"
    repo.mkdir()
    (repo / "app.db").write_bytes(b"")
    assert migrate_users(str(repo)) == 0


def test_migrate_users_skips_already_present(tmp_path):
    repo = tmp_path / "dupu"
    repo.mkdir()
    app_db = repo / "app.db"
    con = sqlite3.connect(app_db)
    con.execute(
        """CREATE TABLE user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(15) UNIQUE,
            email VARCHAR(50) UNIQUE,
            password VARCHAR(80)
        )"""
    )
    con.execute(
        "INSERT INTO user(username, email, password) VALUES (?,?,?)",
        ("u1", "e1@test.com", "h1"),
    )
    con.commit()
    con.close()

    login = repo / "login.db"
    c = sqlite3.connect(login)
    c.execute(
        """CREATE TABLE user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(15) UNIQUE,
            email VARCHAR(50) UNIQUE,
            password VARCHAR(80)
        )"""
    )
    c.execute(
        "INSERT INTO user(username, email, password) VALUES (?,?,?)",
        ("u1", "e1@test.com", "h2"),
    )
    c.commit()
    c.close()

    assert migrate_users(str(repo)) == 0


def test_migrate_users_skips_missing_table(tmp_path):
    repo = tmp_path / "r2"
    repo.mkdir()
    login = repo / "login.db"
    c = sqlite3.connect(login)
    c.execute("CREATE TABLE other (x INT)")
    c.commit()
    c.close()
    (repo / "app.db").write_bytes(b"")

    assert migrate_users(str(repo)) == 0
