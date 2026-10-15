from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from schemas.user_subject_schema import UserSubjectCreate, UserSubjectRead
from services.user_subject_service import user_subject_service

router = APIRouter()


@router.get("/", response_model=list[UserSubjectRead], summary="Список связей user-subject")
async def list_user_subjects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    db: AsyncSession = Depends(get_async_db),
):
    return await user_subject_service.list_user_subjects(
        db, skip=skip, limit=limit, user_id=user_id, subject_id=subject_id,
    )


@router.get("/{user_id}/{subject_id}", response_model=UserSubjectRead, summary="Связь по паре ID")
async def get_user_subject(user_id: int, subject_id: int, db: AsyncSession = Depends(get_async_db)):
    return await user_subject_service.get_user_subject_with_relations_or_404(db, user_id, subject_id)


@router.post("/", response_model=UserSubjectRead, status_code=status.HTTP_201_CREATED,
             summary="Привязать предмет к пользователю")
async def create_user_subject(data: UserSubjectCreate, db: AsyncSession = Depends(get_async_db)):
    return await user_subject_service.create_user_subject(db, data)


@router.delete("/{user_id}/{subject_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Отвязать предмет от пользователя")
async def delete_user_subject(user_id: int, subject_id: int, db: AsyncSession = Depends(get_async_db)):
    await user_subject_service.delete_user_subject(db, user_id, subject_id)