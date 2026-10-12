# services/user_service.py
import logging
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from enums.user_enums import SocialNetworkLinkType
from models.models import User
from schemas.user_schema import UserCreate, UserUpdate
from crud.user_crud import

logger = logging.getLogger(__name__)


# ---------- CREATE ----------

async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """Создаёт пользователя. Проверяет уникальность email и соцсетей."""
    existing_email = await user_crud.get_user_by_email(db, data.email)
    if existing_email is not None:
        logger.info("Отказ в создании пользователя: email уже занят email=%s", data.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Пользователь с email={data.email} уже существует",
        )

    _check_social_conflicts_in_payload(data)

    try:
        user = await user_crud.create_user(db, data)
    except Exception as e:
        # IntegrityError и прочее уже залогировано в CRUD
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось создать пользователя (нарушение целостности данных)",
        ) from e

    logger.info("Создан пользователь id=%s email=%s", user.id, user.email)
    return user


def _check_social_conflicts_in_payload(data: UserCreate) -> None:
    """Проверяет, что в payload не переданы конфликтующие соцсети (по типам)."""
    provided = []
    for link_type, field in user_crud._SOCIAL_FIELD_MAP.items():
        value = getattr(data, field, None)
        if value is not None:
            provided.append((link_type, field, value))
    # сейчас просто логируем — явные конфликты ловит БД
    if provided:
        logger.debug("create_user: указаны соцсети %s", provided)


# ---------- READ ----------

async def get_user_or_404(db: AsyncSession, user_id: int) -> User:
    user = await user_crud.get_user(db, user_id)
    if user is None:
        logger.info("Пользователь не найден: id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь id={user_id} не найден",
        )
    return user


async def get_user_with_relations_or_404(db: AsyncSession, user_id: int) -> User:
    user = await user_crud.get_user_with_relations(db, user_id)
    if user is None:
        logger.info("Пользователь не найден (со связями): id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь id={user_id} не найден",
        )
    return user


async def list_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    group_id: Optional[int] = None,
) -> Sequence[User]:
    """Возвращает список пользователей с пагинацией."""
    try:
        users = await user_crud.get_users(db, skip=skip, limit=limit, group_id=group_id)
    except ValueError as e:
        # CRUD уже проверил параметры — превращаем в HTTP-ошибку
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    logger.info(
        "Получен список пользователей: count=%s skip=%s limit=%s group_id=%s",
        len(users), skip, limit, group_id,
    )
    return users


# ---------- UPDATE ----------

async def update_user(
    db: AsyncSession, user_id: int, data: UserUpdate
) -> User:
    """Обновляет пользователя. Проверяет уникальность email при смене."""
    user = await get_user_or_404(db, user_id)

    update_data = data.model_dump(exclude_unset=True)

    # Проверка уникальности email, если он меняется
    new_email = update_data.get("email")
    if new_email is not None and new_email != user.email:
        existing = await user_crud.get_user_by_email(db, new_email)
        if existing is not None and existing.id != user.id:
            logger.info(
                "Отказ в обновлении: email занят email=%s user_id=%s",
                new_email, user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email={new_email} уже используется другим пользователем",
            )

    try:
        updated = await user_crud.update_user(db, user, data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    if updated is None:
        # CRUD вернул None — трактуем как «не найден»
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь id={user_id} не найден",
        )

    logger.info("Обновлён пользователь id=%s поля=%s", user_id, list(update_data.keys()))
    return updated


# ---------- SOCIAL LINKS ----------

async def link_social(
    db: AsyncSession,
    user_id: int,
    link_type: SocialNetworkLinkType,
    social_id: int | str,
) -> User:
    """Привязывает соцсеть к пользователю с проверкой занятости social_id."""
    user = await get_user_or_404(db, user_id)

    # Пользователь уже с таким social_id?
    existing = await user_crud.get_user_by_social(db, link_type, social_id)
    if existing is not None and existing.id != user.id:
        logger.info(
            "Отказ в привязке соцсети: %s=%s уже занят user_id=%s",
            link_type.value, social_id, existing.id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{link_type.value}={social_id} уже привязан к другому пользователю",
        )

    try:
        linked = await user_crud.link_social(db, user, link_type, social_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    logger.info(
        "Пользователь id=%s привязал соцсеть %s=%s",
        user_id, link_type.value, social_id,
    )
    return linked


async def unlink_social(
    db: AsyncSession,
    user_id: int,
    link_type: SocialNetworkLinkType,
) -> User:
    """Отвязывает соцсеть от пользователя."""
    user = await get_user_or_404(db, user_id)

    field = user_crud._SOCIAL_FIELD_MAP[link_type]
    if getattr(user, field, None) is None:
        logger.info(
            "Отказ в отвязке: у user_id=%s нет привязки %s",
            user_id, link_type.value,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"У пользователя нет привязанного {link_type.value}",
        )

    try:
        unlinked = await user_crud.unlink_social(db, user, link_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    logger.info("Пользователь id=%s отвязал соцсеть %s", user_id, link_type.value)
    return unlinked


async def get_user_by_social_or_404(
    db: AsyncSession,
    link_type: SocialNetworkLinkType,
    social_id: int | str,
) -> User:
    user = await user_crud.get_user_by_social(db, link_type, social_id)
    if user is None:
        logger.info(
            "Пользователь не найден по соцсети: %s=%s", link_type.value, social_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с {link_type.value}={social_id} не найден",
        )
    return user


# ---------- DELETE ----------

async def delete_user(db: AsyncSession, user_id: int) -> None:
    """Удаляет пользователя."""
    user = await get_user_or_404(db, user_id)

    try:
        await user_crud.delete_user(db, user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    logger.info("Удалён пользователь id=%s", user_id)