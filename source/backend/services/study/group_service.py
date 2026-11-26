from __future__ import annotations

import logging
from typing import Final, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from crud.study.group_crud import group_crud
from schemas.study.study_schema import Group, GroupCreate, GroupUpdate

logger = logging.getLogger(__name__)


class GroupService:
    """Сервис управления группами."""

    def __init__(self) -> None:
        self.crud: Final = group_crud

    async def create_group(self, db: AsyncSession, data: GroupCreate) -> Group:
        existing = await self.crud.get_group_by_name(db, data.name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Группа с именем={data.name!r} уже существует",
            )
        try:
            group = await self.crud.create_group(db, data)
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось создать группу",
            )
        except Exception as e:
            logger.exception("create_group: непредвиденная ошибка")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось создать группу",
            ) from e
        logger.info("create_group: создана group.id=%s", group.id)
        return group

    async def get_group_or_404(self, db: AsyncSession, group_id: int) -> Group:
        group = await self.crud.get_group(db, group_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Группа id={group_id} не найдена",
            )
        return group

    async def get_group_by_name_or_404(self, db: AsyncSession, name: str) -> Group:
        group = await self.crud.get_group_by_name(db, name)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Группа с именем={name!r} не найдена",
            )
        return group

    async def get_group_with_relations_or_404(
        self, db: AsyncSession, group_id: int
    ) -> Group:
        group = await self.crud.get_group_with_relations(db, group_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Группа id={group_id} не найдена",
            )
        return group

    async def list_groups(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Sequence[Group]:
        try:
            groups = await self.crud.get_groups(db, skip=skip, limit=limit)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        logger.info("list_groups: count=%d skip=%s limit=%s", len(groups), skip, limit)
        return groups

    async def update_group(
        self, db: AsyncSession, group_id: int, data: GroupUpdate
    ) -> Group:
        group = await self.get_group_or_404(db, group_id)
        update_data = data.model_dump(exclude_unset=True)
        new_name = update_data.get("name")
        if new_name is not None and new_name != group.name:
            existing = await self.crud.get_group_by_name(db, new_name)
            if existing is not None and existing.id != group.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Имя={new_name!r} уже используется другой группой",
                )
        try:
            updated = await self.crud.update_group(db, group, data)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось обновить группу",
            )
        logger.info("update_group: обновлена group.id=%s", group_id)
        return updated

    async def delete_group(self, db: AsyncSession, group_id: int) -> None:
        group = await self.get_group_or_404(db, group_id)
        try:
            await self.crud.delete_group(db, group)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        logger.info("delete_group: удалена group.id=%s", group_id)


group_service: Final[GroupService] = GroupService()
