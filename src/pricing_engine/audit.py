"""Audit trail universel : qui a fait quoi, quand, sur quelle entité.

Architecture :
- Modèle Pydantic `AuditEntry` pour les mutations qu'on enregistre
- Store pluggable `AuditStore` : InMemory (dev/tests) + SqlAlchemy (prod)
- Helper global `log_audit(...)` utilisé dans les endpoints critiques
- Middleware FastAPI qui enrichit chaque entry avec IP + HTTP context

Usage dans un endpoint :
    log_audit(
        actor=user, action="SUBMIT", entity_type="Quote",
        entity_id=str(quote_id),
        details={"status_before": "draft", "status_after": "submitted"},
    )

Les champs `http_path`, `http_method`, `ip_address` sont renseignés
automatiquement par le middleware depuis le contexte de la requête.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# Contexte HTTP accessible depuis log_audit() sans propager la requête
_http_context: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "http_context", default=None
)


class AuditEntry(BaseModel):
    """Entrée du journal d'audit."""

    audit_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_email: str
    actor_role: str = ""
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    http_path: str | None = None
    http_method: str | None = None
    ip_address: str | None = None


class AuditStore(Protocol):
    def append(self, entry: AuditEntry) -> AuditEntry: ...
    def list(
        self, *,
        actor_email: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]: ...


class InMemoryAuditStore:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append(self, entry: AuditEntry) -> AuditEntry:
        self._entries.append(entry)
        return entry

    def list(self, *, actor_email=None, entity_type=None,
             entity_id=None, action=None, limit=100) -> list[AuditEntry]:
        items = list(reversed(self._entries))  # Le plus récent d'abord
        if actor_email is not None:
            items = [e for e in items if e.actor_email.lower() == actor_email.lower()]
        if entity_type is not None:
            items = [e for e in items if e.entity_type == entity_type]
        if entity_id is not None:
            items = [e for e in items if e.entity_id == entity_id]
        if action is not None:
            items = [e for e in items if e.action == action]
        return items[:limit]


# ---------------- Store global + helpers ----------------

_audit_store: AuditStore = InMemoryAuditStore()


def set_audit_store(store: AuditStore) -> None:
    """Appelé par `api.py` au boot pour injecter le store choisi (SQL en prod)."""
    global _audit_store
    _audit_store = store


def get_audit_store() -> AuditStore:
    return _audit_store


def set_http_context(*, path: str, method: str, ip: str | None) -> None:
    _http_context.set({"path": path, "method": method, "ip": ip})


def clear_http_context() -> None:
    _http_context.set(None)


def log_audit(
    *,
    actor_email: str,
    actor_role: str = "",
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any] | None = None,
) -> AuditEntry:
    """Enregistre une mutation dans le journal d'audit.

    Les champs HTTP viennent automatiquement du contextvar renseigné par
    le middleware. En dehors d'une requête HTTP (script, test unitaire),
    ils restent None sans erreur."""
    ctx = _http_context.get() or {}
    entry = AuditEntry(
        actor_email=actor_email,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        http_path=ctx.get("path"),
        http_method=ctx.get("method"),
        ip_address=ctx.get("ip"),
    )
    _audit_store.append(entry)
    return entry
