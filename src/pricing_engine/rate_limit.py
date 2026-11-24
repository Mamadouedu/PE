"""Rate limiting pour les tentatives de login.

Protège contre le brute force sur mots de passe en limitant le nombre
d'échecs consécutifs par email et par IP.

Politique :
- 5 échecs consécutifs sur un email → verrouillage 15 minutes
- Un login réussi reset le compteur de l'email
- Le même scan appliqué sur l'IP : 20 échecs par IP sur 15 minutes
  (plus laxiste parce que une entreprise sort par un seul NAT)

Les verrous expirent automatiquement. Pas de déverrouillage manuel
nécessaire pour l'instant (à ajouter via endpoint admin si demandé).

Deux implémentations :
- InMemory : dict + TTL coté app, OK pour mono-process
- Redis : clés INCR avec TTL natif, partagé entre workers uvicorn
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol


MAX_ECHECS_EMAIL = 5
MAX_ECHECS_IP = 20
FENETRE_SECONDES = 15 * 60  # 15 minutes


@dataclass
class VerificationResult:
    autorise: bool
    raison: str | None = None
    retry_after_seconds: int | None = None


class RateLimiter(Protocol):
    def verifier_et_incrementer(
        self, email: str, ip: str | None,
    ) -> VerificationResult: ...
    def reset(self, email: str) -> None: ...


class InMemoryRateLimiter:
    """Store les timestamps des échecs récents par clé. GC paresseux :
    on nettoie les timestamps hors fenêtre à chaque appel."""

    def __init__(self) -> None:
        self._echecs: dict[str, list[float]] = {}

    @staticmethod
    def _email_key(email: str) -> str:
        return f"email:{email.lower()}"

    @staticmethod
    def _ip_key(ip: str) -> str:
        return f"ip:{ip}"

    def _nettoyer_et_compter(self, key: str, now: float) -> int:
        """Retire les timestamps hors fenêtre et renvoie le nombre restant."""
        bornes = self._echecs.get(key, [])
        encore_dans_fenetre = [t for t in bornes if now - t < FENETRE_SECONDES]
        if encore_dans_fenetre:
            self._echecs[key] = encore_dans_fenetre
        else:
            self._echecs.pop(key, None)
        return len(encore_dans_fenetre)

    def verifier_et_incrementer(
        self, email: str, ip: str | None,
    ) -> VerificationResult:
        now = time.time()
        ek = self._email_key(email)
        count_email = self._nettoyer_et_compter(ek, now)
        if count_email >= MAX_ECHECS_EMAIL:
            # Retry-after = temps jusqu'à expiration du plus ancien
            plus_ancien = min(self._echecs[ek])
            retry = int(FENETRE_SECONDES - (now - plus_ancien)) + 1
            return VerificationResult(
                autorise=False, raison="trop_de_tentatives_email",
                retry_after_seconds=retry,
            )
        if ip:
            ik = self._ip_key(ip)
            count_ip = self._nettoyer_et_compter(ik, now)
            if count_ip >= MAX_ECHECS_IP:
                plus_ancien = min(self._echecs[ik])
                retry = int(FENETRE_SECONDES - (now - plus_ancien)) + 1
                return VerificationResult(
                    autorise=False, raison="trop_de_tentatives_ip",
                    retry_after_seconds=retry,
                )
        # OK : on enregistre l'échec maintenant. Si le login réussit
        # derrière, reset() le retirera.
        self._echecs.setdefault(ek, []).append(now)
        if ip:
            self._echecs.setdefault(self._ip_key(ip), []).append(now)
        return VerificationResult(autorise=True)

    def reset(self, email: str) -> None:
        self._echecs.pop(self._email_key(email), None)


class RedisRateLimiter:
    """Implémentation Redis : compteur INCR par clé avec TTL natif.

    Deux clés par échec : une par email, une par IP. L'INCR est
    atomique ; EXPIRE est posé au 1er incrément via NX (SET IF NOT
    EXISTS) via le helper d'expire-on-first-set. Pour rester simple,
    on utilise un pipeline qui pose EXPIRE si la clé vient d'être
    créée (INCR renvoie 1).
    """

    _KEY_PREFIX = "pricinghub:ratelimit:"

    def __init__(self, redis_client) -> None:
        self._r = redis_client

    def _email_key(self, email: str) -> str:
        return f"{self._KEY_PREFIX}email:{email.lower()}"

    def _ip_key(self, ip: str) -> str:
        return f"{self._KEY_PREFIX}ip:{ip}"

    def _count(self, key: str) -> int:
        val = self._r.get(key)
        if val is None:
            return 0
        return int(val)

    def _ttl(self, key: str) -> int:
        """TTL en secondes, -1 si pas de TTL, -2 si clé absente."""
        return int(self._r.ttl(key))

    def verifier_et_incrementer(
        self, email: str, ip: str | None,
    ) -> VerificationResult:
        ek = self._email_key(email)
        count_email = self._count(ek)
        if count_email >= MAX_ECHECS_EMAIL:
            retry = max(self._ttl(ek), 1)
            return VerificationResult(
                autorise=False, raison="trop_de_tentatives_email",
                retry_after_seconds=retry,
            )
        if ip:
            ik = self._ip_key(ip)
            count_ip = self._count(ik)
            if count_ip >= MAX_ECHECS_IP:
                retry = max(self._ttl(ik), 1)
                return VerificationResult(
                    autorise=False, raison="trop_de_tentatives_ip",
                    retry_after_seconds=retry,
                )

        # Incrément atomique + EXPIRE si nouvelle clé
        with self._r.pipeline() as p:
            p.incr(ek)
            p.expire(ek, FENETRE_SECONDES, nx=True)
            if ip:
                p.incr(self._ip_key(ip))
                p.expire(self._ip_key(ip), FENETRE_SECONDES, nx=True)
            p.execute()
        return VerificationResult(autorise=True)

    def reset(self, email: str) -> None:
        self._r.delete(self._email_key(email))


def make_rate_limiter(redis_client=None) -> RateLimiter:
    if redis_client is None:
        return InMemoryRateLimiter()
    return RedisRateLimiter(redis_client)
