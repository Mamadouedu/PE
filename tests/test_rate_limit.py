"""Tests du rate limiter login (brute force protection)."""

from __future__ import annotations

import importlib
import time

import fakeredis
import pytest
from fastapi.testclient import TestClient

from pricing_engine.rate_limit import (
    FENETRE_SECONDES,
    MAX_ECHECS_EMAIL,
    MAX_ECHECS_IP,
    InMemoryRateLimiter,
    RedisRateLimiter,
    make_rate_limiter,
)


# =========================================================================
# Factory
# =========================================================================


def test_factory_sans_redis_donne_inmemory():
    assert isinstance(make_rate_limiter(None), InMemoryRateLimiter)


def test_factory_avec_redis_donne_redis():
    r = fakeredis.FakeRedis()
    assert isinstance(make_rate_limiter(r), RedisRateLimiter)


# =========================================================================
# InMemoryRateLimiter
# =========================================================================


def test_inmem_autorise_les_premiers_echecs():
    rl = InMemoryRateLimiter()
    for _ in range(MAX_ECHECS_EMAIL - 1):
        assert rl.verifier_et_incrementer("x@y.com", "1.1.1.1").autorise is True


def test_inmem_bloque_au_5eme_echec_email():
    rl = InMemoryRateLimiter()
    for _ in range(MAX_ECHECS_EMAIL):
        rl.verifier_et_incrementer("x@y.com", "1.1.1.1")
    result = rl.verifier_et_incrementer("x@y.com", "1.1.1.1")
    assert result.autorise is False
    assert result.raison == "trop_de_tentatives_email"
    assert result.retry_after_seconds > 0
    assert result.retry_after_seconds <= FENETRE_SECONDES + 1


def test_inmem_reset_apres_succes():
    rl = InMemoryRateLimiter()
    for _ in range(MAX_ECHECS_EMAIL - 1):
        rl.verifier_et_incrementer("x@y.com", "1.1.1.1")
    rl.reset("x@y.com")
    # Après reset on repart à 0
    assert rl.verifier_et_incrementer("x@y.com", "1.1.1.1").autorise is True


def test_inmem_bloque_par_ip_meme_si_emails_differents():
    """Quelqu'un qui teste 20 emails depuis la même IP doit être bloqué."""
    rl = InMemoryRateLimiter()
    for i in range(MAX_ECHECS_IP):
        rl.verifier_et_incrementer(f"user{i}@y.com", "9.9.9.9")
    # Encore un email différent → bloqué par l'IP
    result = rl.verifier_et_incrementer("nouveau@y.com", "9.9.9.9")
    assert result.autorise is False
    assert result.raison == "trop_de_tentatives_ip"


def test_inmem_ip_none_desactive_le_scan_ip():
    rl = InMemoryRateLimiter()
    # Sans IP (test interne), seul le compteur email joue
    for _ in range(MAX_ECHECS_EMAIL):
        rl.verifier_et_incrementer("x@y.com", None)
    # 100 autres emails sans IP : chacun autorisé (jusqu'à leurs 5)
    for i in range(100):
        assert rl.verifier_et_incrementer(f"a{i}@y.com", None).autorise is True


def test_inmem_fenetre_expire_apres_delai(monkeypatch):
    rl = InMemoryRateLimiter()
    now = [1_000_000.0]
    monkeypatch.setattr("pricing_engine.rate_limit.time.time", lambda: now[0])
    for _ in range(MAX_ECHECS_EMAIL):
        rl.verifier_et_incrementer("x@y.com", "1.1.1.1")
    assert rl.verifier_et_incrementer("x@y.com", "1.1.1.1").autorise is False

    # Avance de 16 min : les échecs sortent de la fenêtre
    now[0] += FENETRE_SECONDES + 60
    assert rl.verifier_et_incrementer("x@y.com", "1.1.1.1").autorise is True


# =========================================================================
# RedisRateLimiter
# =========================================================================


def test_redis_bloque_au_5eme_echec():
    rl = RedisRateLimiter(fakeredis.FakeRedis())
    for _ in range(MAX_ECHECS_EMAIL):
        rl.verifier_et_incrementer("x@y.com", "1.1.1.1")
    result = rl.verifier_et_incrementer("x@y.com", "1.1.1.1")
    assert result.autorise is False
    assert result.raison == "trop_de_tentatives_email"
    assert result.retry_after_seconds > 0


def test_redis_reset():
    r = fakeredis.FakeRedis()
    rl = RedisRateLimiter(r)
    for _ in range(MAX_ECHECS_EMAIL - 1):
        rl.verifier_et_incrementer("x@y.com", "1.1.1.1")
    rl.reset("x@y.com")
    assert rl.verifier_et_incrementer("x@y.com", "1.1.1.1").autorise is True


def test_redis_multi_instance():
    """Preuve qu'on peut partager le compteur entre workers uvicorn."""
    r = fakeredis.FakeRedis()
    worker1 = RedisRateLimiter(r)
    worker2 = RedisRateLimiter(r)
    for _ in range(MAX_ECHECS_EMAIL):
        worker1.verifier_et_incrementer("x@y.com", None)
    # worker2 voit le verrouillage posé par worker1
    assert worker2.verifier_et_incrementer("x@y.com", None).autorise is False


def test_redis_expire_est_nx():
    """L'EXPIRE doit être nx=True : ne pas prolonger le TTL à chaque
    nouvel échec (sinon l'attaquant maintient le verrou éternellement
    avec 1 requête / minute)."""
    r = fakeredis.FakeRedis()
    rl = RedisRateLimiter(r)
    rl.verifier_et_incrementer("x@y.com", None)
    ttl1 = r.ttl(RedisRateLimiter._KEY_PREFIX + "email:x@y.com")
    time.sleep(1.1)
    rl.verifier_et_incrementer("x@y.com", None)
    ttl2 = r.ttl(RedisRateLimiter._KEY_PREFIX + "email:x@y.com")
    # ttl2 ne doit pas avoir repris la valeur initiale
    assert ttl2 < ttl1


# =========================================================================
# Intégration API : endpoint /auth/login
# =========================================================================


@pytest.fixture
def client():
    import os
    os.environ.pop("REDIS_URL", None)
    from pricing_engine import api as api_module
    importlib.reload(api_module)
    # Reset du limiter pour isoler les tests entre eux
    api_module._rate_limiter = InMemoryRateLimiter()
    return TestClient(api_module.app), api_module


def test_api_login_429_apres_5_echecs(client):
    c, _ = client
    for _ in range(MAX_ECHECS_EMAIL):
        r = c.post("/api/v1/auth/login",
                   json={"email": "kam1@akiem.com", "mot_de_passe": "FAUX"})
        assert r.status_code == 401
    # Le 6e → 429
    r = c.post("/api/v1/auth/login",
               json={"email": "kam1@akiem.com", "mot_de_passe": "FAUX"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert int(r.headers["Retry-After"]) > 0
    # Le vrai mot de passe est bloqué AUSSI (parce que l'attaquant pourrait
    # guesser juste à ce moment-là)
    r = c.post("/api/v1/auth/login",
               json={"email": "kam1@akiem.com", "mot_de_passe": "kam"})
    assert r.status_code == 429


def test_api_login_succes_reset_le_compteur(client):
    c, _ = client
    # 4 échecs
    for _ in range(MAX_ECHECS_EMAIL - 1):
        c.post("/api/v1/auth/login",
               json={"email": "kam1@akiem.com", "mot_de_passe": "FAUX"})
    # Succès → reset
    r = c.post("/api/v1/auth/login",
               json={"email": "kam1@akiem.com", "mot_de_passe": "kam"})
    assert r.status_code == 200
    # Repart à 0 : on peut retenter 4 fois
    for _ in range(MAX_ECHECS_EMAIL - 1):
        r = c.post("/api/v1/auth/login",
                   json={"email": "kam1@akiem.com", "mot_de_passe": "FAUX"})
        assert r.status_code == 401


def test_api_login_echec_est_audite(client):
    c, api_module = c, _ = client
    c.post("/api/v1/auth/login",
           json={"email": "kam1@akiem.com", "mot_de_passe": "FAUX"})
    auth = {"Authorization": "Bearer " + c.post(
        "/api/v1/auth/login",
        json={"email": "admin@akiem.com", "mot_de_passe": "admin"}
    ).json()["token"]}
    r = c.get("/api/v1/audit?action=LOGIN_FAILED", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["details"]["raison"] == "mdp_invalide"
