import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.main import app

client = TestClient(app)

def mock_get_user_by_username(username: str):
    if username == "admin":
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return {
            "id": 1,
            "username": "admin",
            "password_hash": pwd_context.hash("admin_pass"),
            "rol": "administrador"
        }
    return None

@patch("backend.auth.get_user_by_username", side_effect=mock_get_user_by_username)
def test_login_success(mock_get_user):
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin_pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@patch("backend.auth.get_user_by_username", side_effect=mock_get_user_by_username)
def test_login_wrong_password(mock_get_user):
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "wrong_password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 401

@patch("backend.auth.get_user_by_username", side_effect=mock_get_user_by_username)
def test_login_wrong_user(mock_get_user):
    response = client.post(
        "/auth/login",
        data={"username": "not_admin", "password": "admin_pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 401
