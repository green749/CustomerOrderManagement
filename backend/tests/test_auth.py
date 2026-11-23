import pytest
from app.config import settings


def test_login_success(client):
    res = client.post(
        "/api/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert data["user"]["email"] == settings.admin_email
    assert data["user"]["role"] == "admin"
    assert "refresh_token" in res.cookies


def test_login_invalid_password(client):
    res = client.post(
        "/api/auth/login",
        json={"email": settings.admin_email, "password": "WrongPassword123!"},
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["error"]


def test_get_me_authenticated(client, auth_headers):
    res = client.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == settings.admin_email
    assert data["is_active"] is True


def test_get_me_unauthorized(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_refresh_token_rotation(client):
    # Login to obtain refresh token
    login_res = client.post(
        "/api/auth/login",
        json={"email": settings.demo_email, "password": settings.demo_password},
    )
    assert login_res.status_code == 200
    old_refresh = login_res.json()["refresh_token"]

    # Rotate token
    ref_res = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert ref_res.status_code == 200
    new_data = ref_res.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    assert new_data["refresh_token"] != old_refresh

    # Try reusing old revoked token (should be rejected)
    reuse_res = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse_res.status_code == 401


def test_logout(client):
    login_res = client.post(
        "/api/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    token = login_res.json()["access_token"]
    refresh = login_res.json()["refresh_token"]

    logout_res = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
        json={"refresh_token": refresh},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True

    # Try refreshing with logged out token
    ref_res = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert ref_res.status_code == 401

