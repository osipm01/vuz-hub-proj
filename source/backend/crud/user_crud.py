from typing import Sequence, Optional, Tuple, List

from loguru import logger
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.crud.base import CRUDBase
from src.model.model import Category, Media
from src.schemas.category import CategoryCreate


class CRUDCategory(CRUDBase[Category, CategoryCreate]):
    """CRUD для категорий с медиа и M2M-связями media_category."""

    # ==================== CRUD / GET ====================

    async def get_with_media(
        self, db: AsyncSession, category_id: int
    ) -> Optional[Category]:
        """Получение категории сразу со всеми привязанными медиафайлами."""
        try:
            result = await db.execute(
                select(self.model)
                .where(self.model.id == category_id)
                .options(selectinload(self.model.media))
            )
            category = result.scalars().first()
            if category is None:
                logger.warning(
                    "Категория с id={} не найдена", category_id
                )
            else:
                logger.debug(
                    "Категория id={} получена с медиа ({} шт.)",
                    category_id, len(category.media),
                )
            return category
        except SQLAlchemyError:
            logger.exception(
                "Ошибка БД при получении категории id={} с медиа",
                category_id,
            )
            raise

    async def get_by_name(
        self, db: AsyncSession, name: str
    ) -> Optional[Category]:
        """Поиск по уникальному имени."""
        try:
            result = await db.execute(
                select(self.model).where(self.model.name == name)
            )
            category = result.scalars().first()
            if category is None:
                logger.debug("Категория с именем '{}' не найдена", name)
            return category
        except SQLAlchemyError:
            logger.exception(
                "Ошибка БД при поиске категории по имени '{}'", name
            )
            raise

    async def get_all(self, db: AsyncSession) -> Sequence[Category]:
        """Получение всех категорий."""
        try:
            result = await db.execute(
                select(self.model).order_by(self.model.name)
            )
            categories = result.scalars().all()
            logger.debug("Получено категорий: {}", len(categories))
            return categories
        except SQLAlchemyError:
            logger.exception("Ошибка БД при получении списка категорий")
            raise

    async def get_all_with_media_count(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Tuple[Category, int]]:
        """Получение всех категорий с количеством медиа."""
        if skip < 0 or limit <= 0:
            logger.warning(
                "Некорректные параметры пагинации: skip={} limit={}",
                skip, limit,
            )
            raise ValueError(
                f"Некорректные параметры пагинации: skip={skip}, limit={limit}"
            )
        try:
            result = await db.execute(
                select(self.model, func.count(Media.id))
                .outerjoin(self.model.media)
                .group_by(self.model.id)
                .order_by(self.model.name)
                .offset(skip)
                .limit(limit)
            )
            rows = result.all()
            logger.debug(
                "Получено категорий с медиа-счётчиком: {} (skip={}, limit={})",
                len(rows), skip, limit,
            )
            return rows
        except SQLAlchemyError:
            logger.exception(
                "Ошибка БД при получении категорий с количеством медиа "
                "(skip={}, limit={})",
                skip, limit,
            )
            raise

    # ==================== MEDIA LINKS ====================

    async def add_media(
        self,
        db: AsyncSession,
        category_id: int,
        media_id: int,
    ) -> None:
        """Добавить медиа в категорию (идемпотентно)."""
        try:
            await db.execute(
                text(
                    "INSERT INTO media_category (media_id, category_id) "
                    "VALUES (:media_id, :category_id) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"media_id": media_id, "category_id": category_id},
            )
            await db.commit()
            logger.info(
                "Медиа id={} добавлено в категорию id={}",
                media_id, category_id,
            )
        except IntegrityError:
            await db.rollback()
            logger.error(
                "Нарушение целостности при добавлении медиа id={} "
                "в категорию id={} (неверный id?)",
                media_id, category_id,
            )
            raise
        except SQLAlchemyError:
            await db.rollback()
            logger.exception(
                "Ошибка БД при добавлении медиа id={} в категорию id={}",
                media_id, category_id,
            )
            raise

    async def remove_media(
        self,
        db: AsyncSession,
        category_id: int,
        media_id: int,
    ) -> None:
        """Удалить медиа из категории."""
        try:
            result = await db.execute(
                text(
                    "DELETE FROM media_category "
                    "WHERE media_id = :media_id AND category_id = :category_id"
                ),
                {"media_id": media_id, "category_id": category_id},
            )
            await db.commit()
            if result.rowcount == 0:
                logger.warning(
                    "Связь медиа id={} с категорией id={} не найдена — "
                    "нечего удалять",
                    media_id, category_id,
                )
            else:
                logger.info(
                    "Медиа id={} удалено из категории id={}",
                    media_id, category_id,
                )
        except SQLAlchemyError:
            await db.rollback()
            logger.exception(
                "Ошибка БД при удалении медиа id={} из категории id={}",
                media_id, category_id,
            )
            raise

    async def check_media_exists(
        self,
        db: AsyncSession,
        category_id: int,
        media_id: int,
    ) -> bool:
        """Проверить, существует ли связь между категорией и медиа."""
        try:
            result = await db.execute(
                text(
                    "SELECT 1 FROM media_category "
                    "WHERE media_id = :media_id AND category_id = :category_id"
                ),
                {"media_id": media_id, "category_id": category_id},
            )
            exists = result.scalar() is not None
            logger.debug(
                "Проверка связи медиа id={} ↔ категория id={}: {}",
                media_id, category_id, exists,
            )
            return exists
        except SQLAlchemyError:
            logger.exception(
                "Ошибка БД при проверке связи медиа id={} и категории id={}",
                media_id, category_id,
            )
            raise

    async def get_media_ids(
        self, db: AsyncSession, category_id: int
    ) -> List[int]:
        """Получить все media_id для категории."""
        try:
            result = await db.execute(
                text(
                    "SELECT media_id FROM media_category "
                    "WHERE category_id = :category_id"
                ),
                {"category_id": category_id},
            )
            ids = [row[0] for row in result.all()]
            logger.debug(
                "Для категории id={} найдено media_id: {}",
                category_id, len(ids),
            )
            return ids
        except SQLAlchemyError:
            logger.exception(
                "Ошибка БД при получении media_id для категории id={}",
                category_id,
            )
            raise

    # ==================== CASCADE DELETE ====================

    async def cascade_delete_category(
        self, db: AsyncSession, category_id: int
    ) -> None:
        """Каскадное удаление категории.

        1. Проверяет существование.
        2. Удаляет связи в media_category.
        3. Удаляет саму категорию.
        """
        try:
            category = await self.get(db, category_id)
            if category is None:
                logger.warning(
                    "Каскадное удаление пропущено: категория id={} не найдена",
                    category_id,
                )
                return

            result = await db.execute(
                text(
                    "DELETE FROM media_category "
                    "WHERE category_id = :category_id"
                ),
                {"category_id": category_id},
            )
            links_deleted = result.rowcount or 0
            logger.debug(
                "Удалено связей media_category для категории id={}: {}",
                category_id, links_deleted,
            )

            await db.delete(category)
            await db.commit()

            logger.info(
                "Категория id={} каскадно удалена (связей удалено: {})",
                category_id, links_deleted,
            )
        except IntegrityError:
            await db.rollback()
            logger.error(
                "Нарушение целостности при каскадном удалении категории id={}",
                category_id,
            )
            raise
        except SQLAlchemyError:
            await db.rollback()
            logger.exception(
                "Ошибка БД при каскадном удалении категории id={}",
                category_id,
            )
            raise


category_crud = CRUDCategory(Category)