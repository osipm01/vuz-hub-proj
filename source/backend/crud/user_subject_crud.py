import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from schemas.user_subject_schema import UserSubjectCreate
from models.models import UserSubject

logger = logging.getLogger(__name__)


class UserSubjectCRUD:
    _instance: Optional["UserSubjectCRUD"] = None
    _initialized: bool = False

    def __new__(cls) -> "UserSubjectCRUD":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self.__class__._initialized = True

    async def create_user_subject(
        self, db: AsyncSession, data: UserSubjectCreate
    ) -> UserSubject:
        logger.debug("create_user_subject: data=%r", data)
        link = UserSubject(**data.model_dump())
        db.add(link)
        try:
            await db.commit()
            await db.refresh(link)
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "IntegrityError in create_user_subject: user_id=%s subject_id=%s err=%s",
                data.user_id, data.subject_id, e,
            )
            raise
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in create_user_subject: err=%s", e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in create_user_subject: err=%s", e)
            raise
        logger.info(
            "create_user_subject: создана связь user_id=%s subject_id=%s",
            link.user_id, link.subject_id,
        )
        return link

    async def get_user_subject(
        self, db: AsyncSession, user_id: int, subject_id: int
    ) -> Optional[UserSubject]:
        logger.debug("get_user_subject: user_id=%s subject_id=%s", user_id, subject_id)
        try:
            result = await db.execute(
                select(UserSubject).where(
                    UserSubject.user_id == user_id,
                    UserSubject.subject_id == subject_id,
                )
            )
            link = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception(
                "SQLAlchemyError in get_user_subject: user_id=%s subject_id=%s err=%s",
                user_id, subject_id, e,
            )
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error in get_user_subject: user_id=%s subject_id=%s err=%s",
                user_id, subject_id, e,
            )
            raise
        if link is None:
            logger.warning(
                "get_user_subject: не найдено user_id=%s subject_id=%s",
                user_id, subject_id,
            )
        return link

    async def get_user_subject_with_relations(
        self, db: AsyncSession, user_id: int, subject_id: int
    ) -> Optional[UserSubject]:
        logger.debug(
            "get_user_subject_with_relations: user_id=%s subject_id=%s",
            user_id, subject_id,
        )
        stmt = (
            select(UserSubject)
            .where(
                UserSubject.user_id == user_id,
                UserSubject.subject_id == subject_id,
            )
            .options(joinedload(UserSubject.user), joinedload(UserSubject.subject))
        )
        try:
            result = await db.execute(stmt)
            link = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_user_subject_with_relations: err=%s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_user_subject_with_relations: err=%s", e)
            raise
        return link

    async def get_user_subjects(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        subject_id: Optional[int] = None,
    ) -> Sequence[UserSubject]:
        logger.debug(
            "get_user_subjects: skip=%s limit=%s user_id=%s subject_id=%s",
            skip, limit, user_id, subject_id,
        )
        if skip < 0 or limit <= 0:
            raise ValueError(f"Некорректные параметры пагинации: skip={skip}, limit={limit}")

        stmt = select(UserSubject)
        if user_id is not None:
            stmt = stmt.where(UserSubject.user_id == user_id)
        if subject_id is not None:
            stmt = stmt.where(UserSubject.subject_id == subject_id)
        stmt = stmt.offset(skip).limit(limit)

        try:
            result = await db.execute(stmt)
            links = result.scalars().all()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_user_subjects: err=%s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_user_subjects: err=%s", e)
            raise
        logger.debug("get_user_subjects: получено %d записей", len(links))
        return links

    async def delete_user_subject(
        self, db: AsyncSession, link: UserSubject
    ) -> bool:
        logger.debug(
            "delete_user_subject: user_id=%s subject_id=%s",
            link.user_id, link.subject_id,
        )
        await db.delete(link)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in delete_user_subject: err=%s", e)
            raise ValueError("Невозможно удалить связь: связанные записи") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in delete_user_subject: err=%s", e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in delete_user_subject: err=%s", e)
            raise
        logger.info(
            "delete_user_subject: удалена связь user_id=%s subject_id=%s",
            link.user_id, link.subject_id,
        )
        return True


user_subject_crud = UserSubjectCRUD()