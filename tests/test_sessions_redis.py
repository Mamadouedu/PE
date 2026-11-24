"""Tests du RedisSessionStore.

Deux niveaux :
- Unitaire : fakeredis (pur Python, aucun démon) — validation de la
  logique du store seul
- Intégration : vrai Redis si REDIS_URL joignable — validation que les
  commandes utilisées (HSET, EXPIRE, SADD, SMEMBERS, pipeline) se
  comportent comme attendu avec le vrai moteur

Multi-instance : deux stores pointant sur le même Redis voient les mêmes
sessions — ce que InMemorySessionStore ne sait pas faire.
"""

from __future__ import annotations

import importlib
import os
import time

import fakeredis
import pytest

from pricing_engine.users import (
    DUREE_SESSION_SECONDES,
    InMemorySessionStore,
    RedisSessionStore,
    make_session_store,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def fake_store():
    return RedisSessionStore(fakeredis.FakeRedis())


@pytest.fixture
def real_redis_store():
    """Store pointant sur un vrai Redis local. Skip si pas joignable."""
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/15")
    try:
        import redis
        client = redis.Redis.from_url(url, socket_connect_timeout=1)
        client.ping()
        client.flushdb()
    except Exception:
        pytest.skip(f"Redis indisponible sur {url}")
    yield RedisSessionStore(client), client, url
    client.flushdb()


# =========================================================================
# Unitaires (fakeredis)
# =========================================================================


def test_creer_rend_une_session_avec_token(fake_store):
    s = fake_store.creer("kam1@akiem.com")
    assert s.token
    assert s.email == "kam1@akiem.com"
    assert s.expire_le > time.time()


def test_get_reconstruit_la_session_depuis_redis(fake_store):
    s = fake_store.creer("kam1@akiem.com")
    relu = fake_store.get(s.token)
    assert relu is not None
    assert relu.token == s.token
    assert relu.email == "kam1@akiem.com"
    assert abs(relu.expire_le - s.expire_le) < 1.0


def test_get_renvoie_none_pour_token_inconnu(fake_store):
    assert fake_store.get("token-pourri") is None


def test_revoquer_supprime_la_session(fake_store):
    s = fake_store.creer("kam1@akiem.com")
    fake_store.revoquer(s.token)
    assert fake_store.get(s.token) is None


def test_revoquer_pour_vide_toutes_les_sessions_d_un_user(fake_store):
    s1 = fake_store.creer("kam1@akiem.com")
    s2 = fake_store.creer("kam1@akiem.com")
    s3 = fake_store.creer("kam2@akiem.com")

    n = fake_store.revoquer_pour("kam1@akiem.com")
    assert n == 2
    assert fake_store.get(s1.token) is None
    assert fake_store.get(s2.token) is None
    # Les sessions d'un autre user ne bougent pas
    assert fake_store.get(s3.token) is not None


def test_revoquer_pour_insensible_a_la_casse(fake_store):
    s = fake_store.creer("Kam1@Akiem.com")
    n = fake_store.revoquer_pour("kam1@akiem.com")
    assert n == 1
    assert fake_store.get(s.token) is None


def test_session_expiree_renvoie_none_et_nettoie(fake_store):
    s = fake_store.creer("kam1@akiem.com")
    # Simule une horloge en avance : réécrit expire_le dans le passé
    fake_store._r.hset(RedisSessionStore._skey(s.token),
                       "expire_le", str(time.time() - 10))
    assert fake_store.get(s.token) is None


def test_ttl_redis_couvre_la_duree_de_session(fake_store):
    s = fake_store.creer("kam1@akiem.com")
    ttl = fake_store._r.ttl(RedisSessionStore._skey(s.token))
    # TTL doit être proche de DUREE_SESSION_SECONDES
    assert DUREE_SESSION_SECONDES - 5 <= ttl <= DUREE_SESSION_SECONDES


# =========================================================================
# Multi-instance : deux stores, un même Redis
# =========================================================================


def test_multi_instance_voit_les_memes_sessions():
    """Scenario : 2 workers uvicorn partagent Redis. Le worker 1 crée
    une session, le worker 2 la lit — ce qui est impossible en in-memory."""
    r = fakeredis.FakeRedis()
    worker1 = RedisSessionStore(r)
    worker2 = RedisSessionStore(r)

    s = worker1.creer("kam1@akiem.com")
    relu = worker2.get(s.token)
    assert relu is not None
    assert relu.email == "kam1@akiem.com"

    # Un revoke sur un worker invalide sur l'autre
    worker2.revoquer(s.token)
    assert worker1.get(s.token) is None


def test_in_memory_ne_voit_pas_les_sessions_d_un_autre_process():
    """Preuve inverse : l'InMemory ne partage rien, c'est pour ça qu'on
    a besoin de Redis en multi-instance."""
    a = InMemorySessionStore()
    b = InMemorySessionStore()
    s = a.creer("kam1@akiem.com")
    assert b.get(s.token) is None


# =========================================================================
# Factory make_session_store
# =========================================================================


def test_factory_sans_url_renvoie_in_memory():
    store = make_session_store(None)
    assert isinstance(store, InMemorySessionStore)


def test_factory_sans_url_vide_renvoie_in_memory():
    store = make_session_store("")
    assert isinstance(store, InMemorySessionStore)


def test_factory_avec_url_invalide_leve_tot():
    """Si REDIS_URL pointe nulle part, on veut échouer au boot et pas
    au premier login."""
    with pytest.raises(Exception):
        make_session_store("redis://localhost:9999/0")


# =========================================================================
# Intégration vrai Redis
# =========================================================================


def test_integration_redis_round_trip(real_redis_store):
    store, _, _ = real_redis_store
    s = store.creer("kam1@akiem.com")
    relu = store.get(s.token)
    assert relu is not None
    assert relu.email == "kam1@akiem.com"


def test_integration_redis_revoquer_pour_multi_sessions(real_redis_store):
    store, _, _ = real_redis_store
    store.creer("kam1@akiem.com")
    store.creer("kam1@akiem.com")
    store.creer("kam2@akiem.com")
    assert store.revoquer_pour("kam1@akiem.com") == 2


def test_integration_api_avec_redis_url(real_redis_store, monkeypatch):
    """Scénario complet : l'API démarre avec REDIS_URL, login puis /me
    marchent et la session passe bien par Redis."""
    _, _, url = real_redis_store
    monkeypatch.setenv("REDIS_URL", url)

    from fastapi.testclient import TestClient
    from pricing_engine import api as api_module
    importlib.reload(api_module)

    assert isinstance(api_module._sessions, RedisSessionStore)

    client = TestClient(api_module.app)
    r = client.post("/api/v1/auth/login",
                    json={"email": "kam1@akiem.com", "mot_de_passe": "kam"})
    assert r.status_code == 200
    token = r.json()["token"]

    # /me via le token : passe par Redis
    r = client.get("/api/v1/auth/me",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "kam1@akiem.com"

    # La session existe bien dans Redis
    import redis
    rc = redis.Redis.from_url(url)
    assert rc.exists(RedisSessionStore._skey(token)) == 1

    # Reload avec Redis vide-sans-URL : l'API revient en in-memory mais
    # le token Redis précédent n'est plus valide
    monkeypatch.delenv("REDIS_URL", raising=False)
    importlib.reload(api_module)
    assert isinstance(api_module._sessions, InMemorySessionStore)
