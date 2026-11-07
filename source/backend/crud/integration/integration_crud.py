from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models.integration import IntegrationLog, IntegrationToken

logger = logging.getLogger(__name__)


class IntegrationCRUD:
    _instance: Optional["IntegrationCRUD"] = None
    _initialized: bool = False

    def __new__(cls) -> "IntegrationCRUD":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self.__class__._initialized = True

    async def create_log(
        self, db: AsyncSession, *,
        endpoint: str, method: str, status_code: int,
        request_data: Optional[str] = None,
        response_data: Optional[str] = None,
    ) -> IntegrationLog:
        logger.debug("create_log: endpoint=%s method=%s status=%s", endpoint, method, status_code)
        log = IntegrationLog(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            request_data=request_data,
            response_data=response_data,
        )
        db.add(log)
        try:
            async with db.begin():
                await db.refresh(log)
        except SQLAlchemyError:
            logger.exception("create_log: SQLAlchemyError")
            raise
        logger.info("create_log: создан log.id=%s", log.id)
        return log

    async def get_logs(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Sequence[IntegrationLog]:
        logger.debug("get_logs: skip=%s limit=%s", skip, limit)
        stmt = select(IntegrationLog).order_by(IntegrationLog.id.desc()).offset(skip).limit(limit)
        try:
            result = await db.execute(stmt)
            logs = result.scalars().all()
        except SQLAlchemyError:
            logger.exception("get_logs: SQLAlchemyError")
            raise
        return logs

    async def create_token(
        self, db: AsyncSession, *,
        name: str, token_hash: str,
        expires_at: Optional[str] = None,
    ) -> IntegrationToken:
        logger.debug("create_token: name=%s", name)
        token = IntegrationToken(name=name, token_hash=token_hash, expires_at=expires_at)
        db.add(token)
        try:
            async with db.begin():
                await db.refresh(token)
        except IntegrityError as e:
            logger.error("create_token: IntegrityError name=%s err=%s", name, e)
            raise
        except SQLAlchemyError:
            logger.exception("create_token: SQLAlchemyError")
            raise
        logger.info("create_token: создан token.id=%s name=%s", token.id, name)
        return token

    async def get_token_by_name(
        self, db: AsyncSession, name: str
    ) -> Optional[IntegrationToken]:
        logger.debug("get_token_by_name: name=%s", name)
        stmt = select(IntegrationToken).where(IntegrationToken.name == name)
        try:
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception("get_token_by_name: SQLAlchemyError")
            raise


integration_crud = IntegrationCRUD()
