"""CRUD над файловым хранилищем задач (jobstore).

Модульный синглтон, только атомарные операции, без бизнес-логики.
Бизнес-правила (лимиты, статусы, HTTPException) — в services.
"""
import logging
from typing import Any, Final

from webapp import jobstore as store

logger: Final[logging.Logger] = logging.getLogger(__name__)


class JobCRUD:
    """Атомарные операции с хранилищем задач."""

    # --- чтение ---
    def get_job(self, job_id: str) -> dict[str, Any] | None:
        if not store.valid_id(job_id):
            return None
        return store.read(job_id)

    def get_mtime_ns(self, job_id: str) -> int:
        return store.mtime_ns(job_id)

    def list_ids(self) -> list[str]:
        return store.all_ids()

    def job_dir(self, job_id: str, create: bool = False) -> Any:
        return store.job_dir(job_id, create=create)

    # --- запись ---
    def create_job(
        self,
        params: dict[str, Any],
        input_name: str | None,
        summary: dict[str, Any],
    ) -> str:
        return store.create(params, input_name, summary)

    def update_job(self, job_id: str, **fields: Any) -> dict[str, Any]:
        return store.update(job_id, **fields)

    def remove_job(self, job_id: str) -> None:
        store.remove(job_id)

    # --- служебное ---
    def cleanup(self, ttl_seconds: float) -> int:
        return store.cleanup(ttl_seconds)

    @staticmethod
    def is_active(status: str | None) -> bool:
        return status in store.ACTIVE

    @staticmethod
    def is_terminal(status: str | None) -> bool:
        return status in store.TERMINAL


job_crud: Final[JobCRUD] = JobCRUD()