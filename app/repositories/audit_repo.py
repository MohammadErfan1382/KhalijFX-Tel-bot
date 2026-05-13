from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditAction, AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        user_id: UUID,
        action: AuditAction,
        performed_by: int | None = None,
        metadata: dict[str, Any] | None = None,
        context: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            performed_by=performed_by,
            metadata=metadata,
            context=context,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry
