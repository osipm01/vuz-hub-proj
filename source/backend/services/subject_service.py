# todo убрать лишние _ в названиях не должно быть типа _instane или instane_
# todo добавить более строеую типищацию


import logging
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.subject_crud import subject_crud
from models.models import Subject
from schemas.subject_schema import SubjectCreate, SubjectUpdate

logger = logging.getLogger(__name__)


class SubjectService:
    _instance: Optional["SubjectService"] = None
    _initialized: bool = False

    def __new__(cls) -> "SubjectService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self._crud = subject_crud
        self.__class__._initialized = True

    async def create_subject(self, db: AsyncSession, data: SubjectCreate) -> Subject:
        existing = await self._crud.get_subject_by_name(db, data.name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Предмет с именем={data.name!r} уже существует",
            )
        try:
            subject = await self._crud.create_subject(db, data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать предмет (нарушение целостности данных)",
            ) from e
        logger.info("create_subject: создан subject.id=%s", subject.id)
        return subject

    async def get_subject_or_404(self, db: AsyncSession, subject_id: int) -> Subject:
        subject = await self._crud.get_subject(db, subject_id)
        if subject is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Предмет id={subject_id} не найден",
            )
        return subject

    async def list_subjects(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Sequence[Subject]:
        try:
            subjects = await self._crud.get_subjects(db, skip=skip, limit=limit)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        logger.info("list_subjects: count=%d skip=%s limit=%s", len(subjects), skip, limit)
        return subjects

    async def update_subject(
        self, db: AsyncSession, subject_id: int, data: SubjectUpdate
    ) -> Subject:
        subject = await self.get_subject_or_404(db, subject_id)

        update_data = data.model_dump(exclude_unset=True)
        new_name = update_data.get("name")
        if new_name is not None and new_name != subject.name:
            existing = await self._crud.get_subject_by_name(db, new_name)
            if existing is not None and existing.id != subject.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Имя={new_name!r} уже используется другим предметом",
                )

        try:
            updated = await self._crud.update_subject(db, subject, data)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Предмет id={subject_id} не найден",
            )
        return updated

    async def delete_subject(self, db: AsyncSession, subject_id: int) -> None:
        subject = await self.get_subject_or_404(db, subject_id)
        try:
            await self._crud.delete_subject(db, subject)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        logger.info("delete_subject: удалён subject.id=%s", subject_id)


subject_service = SubjectService()