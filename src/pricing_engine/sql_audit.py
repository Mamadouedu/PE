"""Audit store SQL."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .audit import AuditEntry
from .catalog.db import AuditLogRow


def _s(u) -> str:
    from uuid import UUID
    return str(u) if isinstance(u, UUID) else u


class SqlAlchemyAuditStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    def append(self, entry: AuditEntry) -> AuditEntry:
        with self._sf() as session:
            session.add(AuditLogRow(
                audit_id=_s(entry.audit_id),
                occurred_at=entry.occurred_at,
                actor_email=entry.actor_email,
                actor_role=entry.actor_role,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                details=entry.details,
                http_path=entry.http_path,
                http_method=entry.http_method,
                ip_address=entry.ip_address,
            ))
            session.commit()
            return entry

    def list(self, *, actor_email=None, entity_type=None,
             entity_id=None, action=None, limit=100) -> list[AuditEntry]:
        with self._sf() as session:
            from sqlalchemy import func
            stmt = select(AuditLogRow)
            if actor_email is not None:
                stmt = stmt.where(func.lower(AuditLogRow.actor_email) == actor_email.lower())
            if entity_type is not None:
                stmt = stmt.where(AuditLogRow.entity_type == entity_type)
            if entity_id is not None:
                stmt = stmt.where(AuditLogRow.entity_id == entity_id)
            if action is not None:
                stmt = stmt.where(AuditLogRow.action == action)
            rows = session.execute(
                stmt.order_by(AuditLogRow.occurred_at.desc()).limit(limit)
            ).scalars().all()
            from uuid import UUID
            return [
                AuditEntry(
                    audit_id=UUID(r.audit_id),
                    occurred_at=r.occurred_at,
                    actor_email=r.actor_email,
                    actor_role=r.actor_role,
                    action=r.action,
                    entity_type=r.entity_type,
                    entity_id=r.entity_id,
                    details=dict(r.details or {}),
                    http_path=r.http_path,
                    http_method=r.http_method,
                    ip_address=r.ip_address,
                )
                for r in rows
            ]
