from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from schemas.subject_schema import SubjectCreate, SubjectRead, SubjectUpdate
from services.subject_service import subject_service

router = APIRouter()


@router.get("/", response_model=list[SubjectRead], summary="Список предметов")
async def list_subjects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_db),
):
    return await subject_service.list_subjects(db, skip=skip, limit=limit)


@router.get("/by-name", response_model=SubjectRead, summary="Предмет по имени")
async def get_subject_by_name(name: str, db: AsyncSession = Depends(get_async_db)):
    return await subject_service.get_subject_by_name_or_404(db, name)


@router.get("/{subject_id}", response_model=SubjectRead, summary="Предмет по ID")
async def get_subject(subject_id: int, db: AsyncSession = Depends(get_async_db)):
    return await subject_service.get_subject_or_404(db, subject_id)


@router.post("/", response_model=SubjectRead, status_code=status.HTTP_201_CREATED, summary="Создать предмет")
async def create_subject(data: SubjectCreate, db: AsyncSession = Depends(get_async_db)):
    return await subject_service.create_subject(db, data)


@router.put("/{subject_id}", response_model=SubjectRead, summary="Обновить предмет")
async def update_subject(subject_id: int, data: SubjectUpdate, db: AsyncSession = Depends(get_async_db)):
    return await subject_service.update_subject(db, subject_id, data)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить предмет")
async def delete_subject(subject_id: int, db: AsyncSession = Depends(get_async_db)):
    await subject_service.delete_subject(db, subject_id)