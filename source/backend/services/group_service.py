import logging
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.group_crud import group_crud
from models.models import Group
from schemas.group_schema import GroupCreate, GroupUpdate

logger = logging.getLogger(__name__)


class GroupService:
    _instance: Optional["GroupService"] = None
    _initialized: bool = False

    def __new__(cls) -> "GroupService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self._crud = group_crud
        self.__class__._initialized = True

    async def create_group(self, db: AsyncSession, data: GroupCreate) -> Group:
        existing = await self._crud.get_group_by_name(db, data.name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Группа с именем={data.name!r} уже существует",
            )
        try:
            group = await self._crud.create_group(db, data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось создать группу (нарушение целостности данных)",
            ) from e
        logger.info("create_group: создана group.id=%s", group.id)
        return group

    async def get_group_or_404(self, db: AsyncSession, group_id: int) -> Group:
        group = await self._crud.get_group(db, group_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Группа id={group_id} не найдена",
            )
        return group

    async def get_group_with_relations_or_404(
        self, db: AsyncSession, group_id: int
    ) -> Group:
        group = await self._crud.get_group_with_relations(db, group_id)
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
            groups = await self._crud.get_groups(db, skip=skip, limit=limit)
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
            existing = await self._crud.get_group_by_name(db, new_name)
            if existing is not None and existing.id != group.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Имя={new_name!r} уже используется другой группой",
                )

        try:
            updated = await self._crud.update_group(db, group, data)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Группа id={group_id} не найдена",
            )
        return updated

    async def delete_group(self, db: AsyncSession, group_id: int) -> None:
        group = await self.get_group_or_404(db, group_id)
        try:
            await self._crud.delete_group(db, group)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        logger.info("delete_group: удалена group.id=%s", group_id)


group_service = GroupService()