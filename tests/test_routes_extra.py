import time


def test_index_redirects_unauthenticated_to_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers.get("Location", "")


def test_favicon_returns_file_or_redirect(client):
    r = client.get("/favicon.ico")
    assert r.status_code in (200, 304, 404)


def test_logout_redirects(client):
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code == 302


def test_login_bad_password_redirects_to_login(client, create_user):
    create_user(username="bobby", email="b@example.com", password="password123")
    r = client.post(
        "/login",
        data={"username": "bobby", "password": "wrongpassword"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "/login" in r.headers.get("Location", "")


def test_login_when_already_authenticated_redirects_dashboard(client, create_user):
    create_user()
    client.post("/login", data={"username": "alice", "password": "password123"})
    r = client.get("/login", follow_redirects=False)
    assert r.status_code == 302
    assert "/dashboard" in r.headers.get("Location", "")


def test_index_when_authenticated_redirects_dashboard(client, create_user):
    create_user()
    client.post("/login", data={"username": "alice", "password": "password123"})
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/dashboard" in r.headers.get("Location", "")


def test_wykres_invalid_timespan_defaults_to_day(client, create_user):
    create_user()
    client.post("/login", data={"username": "alice", "password": "password123"})
    r = client.post(
        "/wykres",
        data={"timespan_select": "not-a-real-span"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert b"z ostatniej doby" in r.data or b"ostatniej doby" in r.data


def test_wykres_with_sample_readings(client, create_user, app_module):
    create_user()
    client.post("/login", data={"username": "alice", "password": "password123"})
    now = int(time.time())
    with app_module.app.app_context():
        r = app_module.SensorReading(
            epoch=now,
            humidity=50.0,
            pressure=1000.0,
            temp_hum=22.0,
            temp_prs=21.0,
        )
        app_module.dbl.session.add(r)
        app_module.dbl.session.commit()

    resp = client.get("/wykres")
    assert resp.status_code == 200
    assert b"22" in resp.data or b"50" in resp.data or b"1000" in resp.data


def test_api_history_returns_points_when_readings_exist(client, create_user, app_module):
    create_user()
    client.post("/login", data={"username": "alice", "password": "password123"})
    now_ts = int(time.time())
    with app_module.app.app_context():
        app_module.dbl.session.add(
            app_module.SensorReading(
                epoch=now_ts - 60,
                humidity=40.0,
                pressure=990.0,
                temp_hum=23.0,
                temp_prs=22.0,
            )
        )
        app_module.dbl.session.commit()

    r = client.get("/api/history?span=hour")
    data = r.get_json()
    assert len(data["points"]) >= 1
    assert data["points"][0]["temperature_c"] == 23.0


def test_api_history_spans(client, create_user):
    create_user()
    client.post("/login", data={"username": "alice", "password": "password123"})
    for span in ("hour", "day", "week", "month"):
        r = client.get(f"/api/history?span={span}")
        assert r.status_code == 200
        j = r.get_json()
        assert "points" in j
        assert j["span"] == span
    r = client.get("/api/history?span=unknown")
    assert r.status_code == 200
    assert r.get_json()["span"] == "unknown"


def test_dashboard_renders(client, create_user):
    create_user()
    client.post("/login", data={"username": "alice", "password": "password123"})
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert b"SensorPi" in r.data
