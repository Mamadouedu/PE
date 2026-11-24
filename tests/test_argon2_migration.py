"""Tests Argon2id + migration douce depuis PBKDF2."""

from __future__ import annotations

import hashlib
import secrets

import pytest
from fastapi.testclient import TestClient

from pricing_engine.users import (
    ITERATIONS_PBKDF2,
    hacher_mot_de_passe,
    needs_rehash,
    verifier_mot_de_passe,
)


def test_hacher_produit_un_hash_argon2id():
    h = hacher_mot_de_passe("secret-du-jour")
    assert h.startswith("$argon2id$"), f"Attendu Argon2id, reçu {h[:20]}"
    assert len(h) > 60  # Format PHC standard


def test_verifier_argon2id():
    h = hacher_mot_de_passe("secret-du-jour")
    assert verifier_mot_de_passe("secret-du-jour", h) is True
    assert verifier_mot_de_passe("mauvais", h) is False


def test_deux_hash_meme_mdp_differents():
    """Sel aléatoire : deux hash du même mot de passe sont différents."""
    assert hacher_mot_de_passe("x") != hacher_mot_de_passe("x")


def test_compat_pbkdf2_legacy():
    """Un hash PBKDF2 existant (anciens comptes) doit encore se vérifier."""
    # Reconstruis un hash PBKDF2 au format legacy
    sel = secrets.token_bytes(16)
    derive = hashlib.pbkdf2_hmac("sha256", b"secret-legacy", sel, ITERATIONS_PBKDF2)
    legacy_hash = f"pbkdf2${ITERATIONS_PBKDF2}${sel.hex()}${derive.hex()}"

    assert verifier_mot_de_passe("secret-legacy", legacy_hash) is True
    assert verifier_mot_de_passe("mauvais", legacy_hash) is False


def test_needs_rehash_sur_pbkdf2():
    """Un hash PBKDF2 doit toujours demander un rehash."""
    sel = secrets.token_bytes(16)
    derive = hashlib.pbkdf2_hmac("sha256", b"x", sel, ITERATIONS_PBKDF2)
    legacy = f"pbkdf2${ITERATIONS_PBKDF2}${sel.hex()}${derive.hex()}"
    assert needs_rehash(legacy) is True


def test_needs_rehash_sur_argon2id_courant():
    """Un hash Argon2id tout frais ne doit PAS demander de rehash."""
    h = hacher_mot_de_passe("x")
    assert needs_rehash(h) is False


def test_api_migration_automatique_au_login():
    """CRITIQUE : un utilisateur avec hash PBKDF2 migre automatiquement
    vers Argon2id lors du prochain login réussi.

    Utilise un utilisateur ad-hoc créé pour l'occasion pour ne pas
    contaminer les autres tests qui dépendent du mot de passe original."""
    import importlib
    from pricing_engine import api as api_module
    from pricing_engine.users import Role, Utilisateur
    importlib.reload(api_module)
    client = TestClient(api_module.app)

    # Crée un utilisateur dédié avec un hash PBKDF2 legacy
    users = api_module._users
    email_test = "migration-test@akiem.com"
    sel = secrets.token_bytes(16)
    derive = hashlib.pbkdf2_hmac("sha256", b"legacy123", sel, ITERATIONS_PBKDF2)
    legacy_hash = f"pbkdf2${ITERATIONS_PBKDF2}${sel.hex()}${derive.hex()}"
    users.creer(Utilisateur(
        email=email_test, nom="Migration Test", role=Role.KAM,
        hash_mot_de_passe=legacy_hash,
    ))
    assert users.get(email_test).hash_mot_de_passe.startswith("pbkdf2$")

    try:
        r = client.post("/api/v1/auth/login",
            json={"email": email_test, "mot_de_passe": "legacy123"})
        assert r.status_code == 200

        user_apres = users.get(email_test)
        assert user_apres.hash_mot_de_passe.startswith("$argon2id$"), \
            f"Migration douce échouée : hash toujours {user_apres.hash_mot_de_passe[:20]}"

        r2 = client.post("/api/v1/auth/login",
            json={"email": email_test, "mot_de_passe": "legacy123"})
        assert r2.status_code == 200
    finally:
        # Nettoyage pour ne pas polluer les autres tests qui utilisent kam1
        users.supprimer(email_test)
        # Reload pour restaurer l'état normal du module api
        importlib.reload(api_module)
