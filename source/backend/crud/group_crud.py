import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from schemas.group_schema import GroupCreate, GroupUpdate
from models.models import Group

logger = logging.getLogger(__name__)


class GroupCRUD:
    """Синглтон-репозиторий для работы с группами."""

    _instance: Optional["GroupCRUD"] = None
    _initialized: bool = False

    def __new__(cls) -> "GroupCRUD":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self.__class__._initialized = True

    # ---------- CREATE ----------

    async def create_group(self, db: AsyncSession, data: GroupCreate) -> Group:
        logger.debug("create_group: data=%r", data)
        group = Group(**data.model_dump())
        db.add(group)
        try:
            await db.commit()
            await db.refresh(group)
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "IntegrityError in create_group: name=%r, err=%s",
                getattr(data, "name", None), e,
            )
            raise
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in create_group: err=%s", e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in create_group: err=%s", e)
            raise

        logger.info("create_group: создана group.id=%s name=%r", group.id, group.name)
        return group

    # ---------- READ ----------

    async def get_group(self, db: AsyncSession, group_id: int) -> Optional[Group]:
        logger.debug("get_group: id=%s", group_id)
        try:
            result = await db.execute(select(Group).where(Group.id == group_id))
            group = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_group: id=%s, err=%s", group_id, e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_group: id=%s, err=%s", group_id, e)
            raise

        if group is None:
            logger.warning("get_group: группа не найдена, id=%s", group_id)
        return group

    async def get_group_by_name(self, db: AsyncSession, name: str) -> Optional[Group]:
        logger.debug("get_group_by_name: name=%r", name)
        try:
            result = await db.execute(select(Group).where(Group.name == name))
            group = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_group_by_name: name=%r, err=%s", name, e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_group_by_name: name=%r, err=%s", name, e)
            raise

        if group is None:
            logger.warning("get_group_by_name: не найдена, name=%r", name)
        return group

    async def get_group_with_relations(
        self, db: AsyncSession, group_id: int
    ) -> Optional[Group]:
        logger.debug("get_group_with_relations: id=%s", group_id)
        stmt = (
            select(Group)
            .where(Group.id == group_id)
            .options(
                selectinload(Group.users),
                selectinload(Group.schedules),
            )
        )
        try:
            result = await db.execute(stmt)
            group = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception(
                "SQLAlchemyError in get_group_with_relations: id=%s, err=%s", group_id, e
            )
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error in get_group_with_relations: id=%s, err=%s", group_id, e
            )
            raise

        if group is None:
            logger.warning("get_group_with_relations: не найдена, id=%s", group_id)
        return group

    async def get_groups(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Sequence[Group]:
        logger.debug("get_groups: skip=%s, limit=%s", skip, limit)
        if skip < 0 or limit <= 0:
            logger.error("get_groups: некорректные параметры skip=%s limit=%s", skip, limit)
            raise ValueError(f"Некорректные параметры пагинации: skip={skip}, limit={limit}")

        stmt = select(Group).order_by(Group.id).offset(skip).limit(limit)
        try:
            result = await db.execute(stmt)
            groups = result.scalars().all()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_groups: err=%s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_groups: err=%s", e)
            raise

        logger.debug("get_groups: получено %d записей", len(groups))
        return groups

    # ---------- UPDATE ----------

    async def update_group(
        self, db: AsyncSession, group: Group, data: GroupUpdate
    ) -> Optional[Group]:
        logger.debug("update_group: group.id=%s data=%r", group.id, data)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(group, field, value)

        try:
            await db.commit()
            await db.refresh(group)
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "IntegrityError in update_group: group.id=%s data=%r err=%s",
                group.id, update_data, e,
            )
            raise ValueError("Не удалось обновить группу (дубликат данных)") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in update_group: group.id=%s err=%s", group.id, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in update_group: group.id=%s err=%s", group.id, e)
            raise

        logger.info("update_group: обновлена group.id=%s поля=%s", group.id, list(update_data))
        return group

    # ---------- DELETE ----------

    async def delete_group(self, db: AsyncSession, group: Group) -> bool:
        logger.debug("delete_group: group.id=%s", group.id)
        await db.delete(group)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in delete_group: group.id=%s err=%s", group.id, e)
            raise ValueError("Невозможно удалить группу: существуют связанные записи") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in delete_group: group.id=%s err=%s", group.id, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in delete_group: group.id=%s err=%s", group.id, e)
            raise

        logger.info("delete_group: удалена group.id=%s", group.id)
        return True


group_crud = GroupCRUD()