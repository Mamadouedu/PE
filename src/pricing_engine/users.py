"""Gestion des utilisateurs + authentification.

Modèle simple :
- `Utilisateur` (email, nom, rôle, hash du mot de passe)
- 4 rôles : KAM, PRICING, DIRECTION, ADMIN
- Store pluggable (in-memory, SQL) comme pour le référentiel
- Session tokens aléatoires stockés en mémoire (OK pour un seul process
  uvicorn ; à remplacer par Redis / JWT signé pour un vrai déploiement
  multi-instance)

Hachage des mots de passe : PBKDF2-HMAC-SHA256 via `hashlib.pbkdf2_hmac`
(stdlib, 310_000 itérations — recommandation OWASP 2023). Pas de
dépendance externe (bcrypt/argon2 feraient mieux mais imposeraient une
installation que l'équipe pricing n'a pas forcément).
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


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


def hacher_mot_de_passe(mot_de_passe: str, sel: bytes | None = None) -> str:
    """PBKDF2-HMAC-SHA256. Renvoie une string `pbkdf2$<iterations>$<sel_hex>$<hash_hex>`
    ready à être stockée."""
    if sel is None:
        sel = secrets.token_bytes(16)
    derive = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel, ITERATIONS_PBKDF2)
    return f"pbkdf2${ITERATIONS_PBKDF2}${sel.hex()}${derive.hex()}"


def verifier_mot_de_passe(mot_de_passe: str, hash_stocke: str) -> bool:
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
