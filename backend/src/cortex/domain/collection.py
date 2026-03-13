from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass
class Collection:
    id: UUID
    name: str
    description: str | None = None
    icon: str | None = None
    parent_id: UUID | None = None
    sort_order: int = 0
    filter_json: dict | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_smart(self) -> bool:
        return self.filter_json is not None

    @staticmethod
    def new(
        name: str,
        description: str | None = None,
        icon: str | None = None,
        parent_id: UUID | None = None,
        sort_order: int = 0,
        filter_json: dict | None = None,
    ) -> Collection:
        return Collection(
            id=uuid4(),
            name=name,
            description=description,
            icon=icon,
            parent_id=parent_id,
            sort_order=sort_order,
            filter_json=filter_json,
        )
