def test_signup_post_creates_user_and_returns_success_html(client):
    r = client.post(
        "/signup",
        data={
            "email": "new@example.com",
            "username": "newuser",
            "password": "password123",
            "password2": "password123",
        },
    )
    assert r.status_code == 200
    assert b"New user has been created" in r.data


def test_signup_duplicate_user_returns_error_html(client):
    client.post(
        "/signup",
        data={
            "email": "dup@example.com",
            "username": "dupuser",
            "password": "password123",
            "password2": "password123",
        },
    )
    r = client.post(
        "/signup",
        data={
            "email": "dup@example.com",
            "username": "dupuser",
            "password": "password123",
            "password2": "password123",
        },
    )
    assert r.status_code == 200
    # Should fail form validation via unique checks and re-render page with errors
    assert b"Please use a different" in r.data

