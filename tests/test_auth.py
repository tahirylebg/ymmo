import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.deps import require_roles, require_staff
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import LoginThrottle, TooManyAttemptsError, login_throttle
from app.core.security import ACCESS_COOKIE_NAME, hash_password, verify_password
from app.main import templates
from app.models.enums import UserRole
from tests.factories import make_agency, make_agent

VALID = {
    "email": "Jeanne.Durand@example.fr",
    "password": "Sup3rSecret!",
    "first_name": "Jeanne",
    "last_name": "Durand",
}


@pytest.fixture(autouse=True)
def _reset_throttle():
    login_throttle._failures.clear()
    yield
    login_throttle._failures.clear()


def _register(client, **overrides):
    return client.post("/api/auth/register", json={**VALID, **overrides})


def test_password_is_hashed_with_argon2():
    hashed = hash_password("Sup3rSecret!")
    assert hashed.startswith("$argon2id$")
    assert verify_password("Sup3rSecret!", hashed)
    assert not verify_password("wrong", hashed)


def test_register_creates_a_client(client):
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "client" and body["email"] == "jeanne.durand@example.fr"
    assert "password" not in str(body)


def test_register_rejects_duplicate_email_case_insensitive(client):
    _register(client)
    assert _register(client, email="JEANNE.durand@example.fr").status_code == 409


@pytest.mark.parametrize("password", ["short1A", "alllowercase1", "ALLUPPERCASE1", "NoDigitsHere"])
def test_register_enforces_password_policy(client, password):
    assert _register(client, password=password).status_code == 422


def test_login_sets_httponly_cookie_and_me_works(client):
    _register(client)
    response = client.post(
        "/api/auth/login", json={"email": VALID["email"], "password": VALID["password"]}
    )
    assert response.status_code == 200
    cookie_header = response.headers["set-cookie"]
    assert ACCESS_COOKIE_NAME in cookie_header and "HttpOnly" in cookie_header
    assert "samesite=lax" in cookie_header.lower()

    me = client.get("/api/auth/me")  # TestClient keeps the cookie
    assert me.status_code == 200 and me.json()["first_name"] == "Jeanne"


def test_bearer_token_works_without_cookie(client):
    _register(client)
    token = client.post(
        "/api/auth/token", data={"username": VALID["email"], "password": VALID["password"]}
    ).json()["access_token"]
    client.cookies.clear()
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200


def test_wrong_password_returns_generic_401(client):
    _register(client)
    response = client.post(
        "/api/auth/login", json={"email": VALID["email"], "password": "Wrong-pass1"}
    )
    assert response.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "nobody@x.fr", "password": "x"})
    assert unknown.json()["detail"] == response.json()["detail"]  # no user enumeration


def test_me_requires_authentication(client):
    assert client.get("/api/auth/me").status_code == 401


def test_invalid_token_is_rejected(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_logout_clears_cookie(client):
    _register(client)
    client.post("/api/auth/login", json={"email": VALID["email"], "password": VALID["password"]})
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_login_is_throttled_after_repeated_failures(client):
    _register(client)
    for _ in range(5):
        client.post("/api/auth/login", json={"email": VALID["email"], "password": "Wrong-pass1"})
    response = client.post(
        "/api/auth/login", json={"email": VALID["email"], "password": VALID["password"]}
    )
    assert response.status_code == 429


def test_throttle_unit():
    throttle = LoginThrottle(max_failures=2, window_seconds=60)
    throttle.record_failure("k")
    throttle.check("k")
    throttle.record_failure("k")
    with pytest.raises(TooManyAttemptsError):
        throttle.check("k")
    throttle.reset("k")
    throttle.check("k")


def test_role_guard_blocks_clients_and_allows_staff(client):
    """RBAC dependency tested on a throw-away app to keep it independent of real routes."""
    mini = FastAPI()
    register_exception_handlers(mini, templates)

    @mini.get("/staff")
    def staff_only(user=Depends(require_staff)):
        return {"role": user.role}

    @mini.get("/admin")
    def admin_only(user=Depends(require_roles(UserRole.ADMIN))):
        return {"ok": True}

    db = SessionLocal()
    agent = make_agent(db, make_agency(db), email="agent@ymmo.test")
    agent.password_hash = hash_password(VALID["password"])
    db.commit()
    db.close()

    _register(client)
    client_token = client.post(
        "/api/auth/token", data={"username": VALID["email"], "password": VALID["password"]}
    ).json()["access_token"]
    agent_token = client.post(
        "/api/auth/token", data={"username": "agent@ymmo.test", "password": VALID["password"]}
    ).json()["access_token"]

    with TestClient(mini) as mini_client:
        as_client = {"Authorization": f"Bearer {client_token}"}
        as_agent = {"Authorization": f"Bearer {agent_token}"}
        assert mini_client.get("/staff", headers=as_client).status_code == 403
        assert mini_client.get("/staff", headers=as_agent).json() == {"role": "agent"}
        assert mini_client.get("/admin", headers=as_agent).status_code == 403


def test_security_headers_are_set(client):
    headers = client.get("/").headers
    assert headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in headers["content-security-policy"]
    assert headers["x-content-type-options"] == "nosniff"
