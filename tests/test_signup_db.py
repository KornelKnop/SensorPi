import sqlite3
from unittest.mock import patch


def test_signup_commit_failure_returns_message(client, app_module):
    def boom():
        raise sqlite3.IntegrityError("constraint")

    with patch.object(app_module.dbl.session, "commit", side_effect=boom):
        r = client.post(
            "/signup",
            data={
                "email": "x@example.com",
                "username": "validusr",
                "password": "password123",
                "password2": "password123",
            },
        )
    assert r.status_code == 200
    assert b"Nie uda" in r.data
