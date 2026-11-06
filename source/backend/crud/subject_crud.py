import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.subject_schema import SubjectCreate, SubjectUpdate
from models.models import Subject

logger = logging.getLogger(__name__)


class SubjectCRUD:
    _instance: Optional["SubjectCRUD"] = None
    _initialized: bool = False

    def __new__(cls) -> "SubjectCRUD":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self.__class__._initialized = True

    async def create_subject(self, db: AsyncSession, data: SubjectCreate) -> Subject:
        logger.debug("create_subject: data=%r", data)
        subject = Subject(**data.model_dump())
        db.add(subject)
        try:
            await db.commit()
            await db.refresh(subject)
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in create_subject: name=%r err=%s",
                         getattr(data, "name", None), e)
            raise
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in create_subject: err=%s", e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in create_subject: err=%s", e)
            raise
        logger.info("create_subject: создан subject.id=%s name=%r", subject.id, subject.name)
        return subject

    async def get_subject(self, db: AsyncSession, subject_id: int) -> Optional[Subject]:
        logger.debug("get_subject: id=%s", subject_id)
        try:
            result = await db.execute(select(Subject).where(Subject.id == subject_id))
            subject = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_subject: id=%s err=%s", subject_id, e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_subject: id=%s err=%s", subject_id, e)
            raise
        if subject is None:
            logger.warning("get_subject: не найден id=%s", subject_id)
        return subject

    async def get_subject_by_name(self, db: AsyncSession, name: str) -> Optional[Subject]:
        logger.debug("get_subject_by_name: name=%r", name)
        try:
            result = await db.execute(select(Subject).where(Subject.name == name))
            subject = result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_subject_by_name: name=%r err=%s", name, e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_subject_by_name: name=%r err=%s", name, e)
            raise
        return subject

    async def get_subjects(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Sequence[Subject]:
        logger.debug("get_subjects: skip=%s limit=%s", skip, limit)
        if skip < 0 or limit <= 0:
            raise ValueError(f"Некорректные параметры пагинации: skip={skip}, limit={limit}")
        stmt = select(Subject).order_by(Subject.id).offset(skip).limit(limit)
        try:
            result = await db.execute(stmt)
            subjects = result.scalars().all()
        except SQLAlchemyError as e:
            logger.exception("SQLAlchemyError in get_subjects: err=%s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error in get_subjects: err=%s", e)
            raise
        logger.debug("get_subjects: получено %d записей", len(subjects))
        return subjects

    async def update_subject(
        self, db: AsyncSession, subject: Subject, data: SubjectUpdate
    ) -> Optional[Subject]:
        logger.debug("update_subject: subject.id=%s data=%r", subject.id, data)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(subject, field, value)
        try:
            await db.commit()
            await db.refresh(subject)
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in update_subject: id=%s data=%r err=%s",
                         subject.id, update_data, e)
            raise ValueError("Не удалось обновить предмет (дубликат данных)") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in update_subject: id=%s err=%s", subject.id, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in update_subject: id=%s err=%s", subject.id, e)
            raise
        logger.info("update_subject: обновлён subject.id=%s поля=%s",
                    subject.id, list(update_data))
        return subject

    async def delete_subject(self, db: AsyncSession, subject: Subject) -> bool:
        logger.debug("delete_subject: subject.id=%s", subject.id)
        await db.delete(subject)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.error("IntegrityError in delete_subject: id=%s err=%s", subject.id, e)
            raise ValueError("Невозможно удалить предмет: существуют связанные записи") from e
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("SQLAlchemyError in delete_subject: id=%s err=%s", subject.id, e)
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected error in delete_subject: id=%s err=%s", subject.id, e)
            raise
        logger.info("delete_subject: удалён subject.id=%s", subject.id)
        return True


subject_crud = SubjectCRUD()