"""Gestion des utilisateurs + authentification.

Modèle simple :
- `Utilisateur` (email, nom, rôle, hash du mot de passe)
- 4 rôles : KAM, PRICING, DIRECTION, ADMIN
- Store pluggable (in-memory, SQL) comme pour le référentiel
- Session tokens aléatoires stockés en mémoire (OK pour un seul process
  uvicorn ; à remplacer par Redis / JWT signé pour un vrai déploiement
  multi-instance)

Hachage des mots de passe : **Argon2id** via `argon2-cffi`, winner du
Password Hashing Competition (PHC) et recommandation OWASP 2024.
Memory-hard, résistant GPU/ASIC. Format PHC string (commence par
`$argon2id$`).

Compatibilité ascendante : les anciens hashes PBKDF2 (format
`pbkdf2$<iter>$<sel>$<hash>`) restent vérifiables. Au prochain login
réussi d'un utilisateur PBKDF2, on peut réécrire son hash en Argon2id
via `verifier_et_mettre_a_jour_mot_de_passe()` (migration douce).
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError


class Role(str, Enum):
    KAM = "KAM"
    PRICING = "PRICING"
    DIRECTION = "DIRECTION"
    ADMIN = "ADMIN"


# Permissions dérivées du rôle. Un rôle inclut toutes les permissions des
# rôles inférieurs : ADMIN voit tout, DIRECTION voit l'admin du
# référentiel, PRICING idem, KAM ne voit que ses propres offres.
PERMISSIONS = {
    Role.KAM: {"chiffrer", "voir_ses_offres", "demander_derogation"},
    Role.PRICING: {
        "chiffrer", "voir_ses_offres", "voir_toutes_offres",
        "voir_toutes_derogations", "demander_derogation",
        "admin_referentiel", "import_csv",
    },
    Role.DIRECTION: {
        "chiffrer", "voir_ses_offres", "voir_toutes_offres",
        "voir_toutes_derogations", "demander_derogation", "decider_derogation",
        "admin_referentiel", "publier_referentiel", "import_csv",
    },
    Role.ADMIN: {
        "chiffrer", "voir_ses_offres", "voir_toutes_offres",
        "voir_toutes_derogations", "demander_derogation", "decider_derogation",
        "admin_referentiel", "publier_referentiel", "import_csv",
        "gerer_utilisateurs",
    },
}

ITERATIONS_PBKDF2 = 310_000

# Paramètres Argon2id (OWASP 2024 : balance sécurité/latence <500ms)
# time_cost=3 iterations, memory_cost=64MiB, parallelism=4 lanes
_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    """Argon2id via argon2-cffi. Renvoie une string au format PHC
    (`$argon2id$v=19$m=65536,t=3,p=4$<sel_b64>$<hash_b64>`) prête à
    être stockée. Sel aléatoire généré par argon2-cffi."""
    return _HASHER.hash(mot_de_passe)


def _verifier_pbkdf2_legacy(mot_de_passe: str, hash_stocke: str) -> bool:
    """Compat pour les hashes existants PBKDF2. Au prochain login réussi,
    le hash sera réécrit en Argon2id via `verifier_et_mettre_a_jour`."""
    try:
        schema, iter_s, sel_hex, hash_hex = hash_stocke.split("$")
        if schema != "pbkdf2":
            return False
        iterations = int(iter_s)
        sel = bytes.fromhex(sel_hex)
        attendu = bytes.fromhex(hash_hex)
        derive = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel, iterations)
        return secrets.compare_digest(derive, attendu)
    except (ValueError, AttributeError):
        return False


def verifier_mot_de_passe(mot_de_passe: str, hash_stocke: str) -> bool:
    """Vérifie un mot de passe. Dispatch selon le format du hash :
    - `$argon2id$...` → argon2-cffi verify
    - `pbkdf2$...` → legacy PBKDF2 (anciens comptes)
    """
    if hash_stocke.startswith("$argon2"):
        try:
            return _HASHER.verify(hash_stocke, mot_de_passe)
        except (VerifyMismatchError, InvalidHashError):
            return False
    if hash_stocke.startswith("pbkdf2$"):
        return _verifier_pbkdf2_legacy(mot_de_passe, hash_stocke)
    return False


def needs_rehash(hash_stocke: str) -> bool:
    """True si le hash devrait être réécrit : legacy PBKDF2, ou Argon2id
    avec des paramètres inférieurs à ceux courants."""
    if hash_stocke.startswith("pbkdf2$"):
        return True
    if hash_stocke.startswith("$argon2"):
        try:
            return _HASHER.check_needs_rehash(hash_stocke)
        except InvalidHashError:
            return True
    return True


@dataclass
class Utilisateur:
    email: str
    nom: str
    role: Role
    hash_mot_de_passe: str
    actif: bool = True

    def a_permission(self, permission: str) -> bool:
        return permission in PERMISSIONS.get(self.role, set())


class UserStore(Protocol):
    def get(self, email: str) -> Utilisateur | None: ...
    def lister(self) -> list[Utilisateur]: ...
    def creer(self, utilisateur: Utilisateur) -> None: ...
    def supprimer(self, email: str) -> bool: ...
    def mettre_a_jour(self, utilisateur: Utilisateur) -> None: ...


class InMemoryUserStore:
    def __init__(self) -> None:
        self._utilisateurs: dict[str, Utilisateur] = {}

    def get(self, email: str) -> Utilisateur | None:
        return self._utilisateurs.get(email.lower())

    def lister(self) -> list[Utilisateur]:
        return sorted(self._utilisateurs.values(), key=lambda u: u.email)

    def creer(self, utilisateur: Utilisateur) -> None:
        cle = utilisateur.email.lower()
        if cle in self._utilisateurs:
            raise ValueError(f"Utilisateur {utilisateur.email} existe déjà")
        self._utilisateurs[cle] = utilisateur

    def supprimer(self, email: str) -> bool:
        return self._utilisateurs.pop(email.lower(), None) is not None

    def mettre_a_jour(self, utilisateur: Utilisateur) -> None:
        cle = utilisateur.email.lower()
        if cle not in self._utilisateurs:
            raise KeyError(utilisateur.email)
        self._utilisateurs[cle] = utilisateur


# ---------------- Sessions ----------------

DUREE_SESSION_SECONDES = 8 * 3600  # 8 h — session de travail d'une journée


@dataclass
class Session:
    token: str
    email: str
    expire_le: float = field(default_factory=lambda: time.time() + DUREE_SESSION_SECONDES)

    def expiree(self) -> bool:
        return time.time() > self.expire_le


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def creer(self, email: str) -> Session:
        token = secrets.token_urlsafe(32)
        session = Session(token=token, email=email)
        self._sessions[token] = session
        return session

    def get(self, token: str) -> Session | None:
        session = self._sessions.get(token)
        if session is None:
            return None
        if session.expiree():
            self._sessions.pop(token, None)
            return None
        return session

    def revoquer(self, token: str) -> None:
        self._sessions.pop(token, None)

    def revoquer_pour(self, email: str) -> int:
        """Révoque toutes les sessions d'un utilisateur. Renvoie le nombre révoqué."""
        a_virer = [t for t, s in self._sessions.items() if s.email.lower() == email.lower()]
        for t in a_virer:
            self._sessions.pop(t, None)
        return len(a_virer)
