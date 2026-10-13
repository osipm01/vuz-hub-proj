import logging
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.user_subject_crud import user_subject_crud
from models.models import UserSubject
from schemas.user_subject_schema import UserSubjectCreate

logger = logging.getLogger(__name__)


class UserSubjectService:
    _instance: Optional["UserSubjectService"] = None
    _initialized: bool = False

    def __new__(cls) -> "UserSubjectService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self._crud = user_subject_crud
        self.__class__._initialized = True

    async def create_link(self, db: AsyncSession, data: UserSubjectCreate) -> UserSubject:
        existing = await self._crud.get_user_subject(db, data.user_id, data.subject_id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(f"Связь user_id={data.user_id} subject_id={data.subject_id} "
                        f"уже существует"),
            )
        try:
            link = await self._crud.create_user_subject(db, data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать связь (проверьте user_id и subject_id)",
            ) from e
        logger.info("create_link: создана связь user_id=%s subject_id=%s",
                    link.user_id, link.subject_id)
        return link

    async def get_link_or_404(
        self, db: AsyncSession, user_id: int, subject_id: int
    ) -> UserSubject:
        link = await self._crud.get_user_subject(db, user_id, subject_id)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Связь user_id={user_id} subject_id={subject_id} не найдена",
            )
        return link

    async def get_link_with_relations_or_404(
        self, db: AsyncSession, user_id: int, subject_id: int
    ) -> UserSubject:
        link = await self._crud.get_user_subject_with_relations(db, user_id, subject_id)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Связь user_id={user_id} subject_id={subject_id} не найдена",
            )
        return link

    async def list_links(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        subject_id: Optional[int] = None,
    ) -> Sequence[UserSubject]:
        try:
            links = await self._crud.get_user_subjects(
                db, skip=skip, limit=limit,
                user_id=user_id, subject_id=subject_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        logger.info("list_links: count=%d", len(links))
        return links

    async def delete_link(
        self, db: AsyncSession, user_id: int, subject_id: int
    ) -> None:
        link = await self.get_link_or_404(db, user_id, subject_id)
        try:
            await self._crud.delete_user_subject(db, link)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        logger.info("delete_link: удалена связь user_id=%s subject_id=%s",
                    user_id, subject_id)


user_subject_service = UserSubjectService()