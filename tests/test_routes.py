def test_login_get_ok(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert b"SensorPi" in r.data


def test_signup_get_ok(client):
    r = client.get("/signup")
    assert r.status_code == 200
    assert b"Rejestracja" in r.data


def test_dashboard_requires_login(client):
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers.get("Location", "")


def test_api_now_requires_login(client):
    r = client.get("/api/now", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers.get("Location", "")


def test_login_flow_redirects_to_dashboard(client, create_user):
    create_user(username="bobby", email="bob@example.com", password="password123")
    r = client.post(
        "/login",
        data={"username": "bobby", "password": "password123", "remember": "y"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "/dashboard" in r.headers.get("Location", "")


def test_api_now_after_login_returns_json(client, create_user):
    create_user()
    client.post("/login", data={"username": "alice", "password": "password123"})

    r = client.get("/api/now")
    assert r.status_code == 200
    data = r.get_json()
    assert "available" in data
    assert data["available"]["temperature"] in (True, False)
    assert data["source"] in ("sense_hat", "none")


def test_history_api_after_login_returns_points_list(client, create_user):
    create_user()
    client.post("/login", data={"username": "alice", "password": "password123"})

    r = client.get("/api/history?span=hour")
    assert r.status_code == 200
    data = r.get_json()
    assert "points" in data
    assert isinstance(data["points"], list)


def test_wykres_and_stat_render_after_login(client, create_user):
    create_user()
    client.post("/login", data={"username": "alice", "password": "password123"})

    r1 = client.get("/wykres")
    assert r1.status_code == 200
    r2 = client.get("/stat")
    assert r2.status_code == 200

