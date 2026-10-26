"""Бизнес-логика задач генерации расписания.

Инкапсулирует:
  * валидацию входных параметров и загруженного файла;
  * проверку лимитов (размер файла, число пар, длина очереди, elite<pop);
  * оркестрацию: сохранение файла → валидация → создание задачи → enqueue;
  * отмену/удаление/получение результата;
  * маппинг ошибок в HTTPException (400/404/409/413/422/429).

Не знает про FastAPI-роуты и про процессы воркеров (только через worker_service).
"""
import logging
import time
from pathlib import Path
from typing import Any, Final

from fastapi import HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from crud.job_crud import job_crud
from services.worker_service import worker_service

logger: Final[logging.Logger] = logging.getLogger(__name__)

MAX_LESSONS: Final[int] = 20000
CHUNK: Final[int] = 1 << 20


class GenerateScheduleService:
    def __init__(self) -> None:
        self.crud: Final = job_crud
        self.workers: Final = worker_service

    # ---------- создание ----------
    async def create_job(
        self,
        *,
        file: UploadFile | None,
        pop: int,
        generations: int,
        mutation: float,
        elite: int,
        workers: int,
        device: str,
        seed: int,
        teachers: int,
        groups: int,
        rooms: int,
        max_queue: int,
        max_upload: int,
        cpu: int,
    ) -> str:
        if self.workers.queued_count >= max_queue:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "Очередь переполнена, попробуйте позже")
        if elite >= pop:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "elite должно быть меньше размера популяции")

        params: dict[str, Any] = dict(
            pop=pop, generations=generations, mutation=mutation,
            elite=elite, workers=min(workers, cpu), device=device,
            seed=seed, teachers=teachers, groups=groups, rooms=rooms,
        )

        has_file = file is not None and bool(file.filename)
        if has_file and not file.filename.lower().endswith((".xlsx", ".xlsm")):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Нужен файл .xlsx")

        jid = self.crud.create_job(
            params, file.filename if has_file else None, {},
        )
        try:
            if has_file:
                dest = self.crud.job_dir(jid, create=True) / "input.xlsx"
                await self._save_upload(file, dest, max_upload)
                summary = await self._check_input(str(dest))
                if summary["lessons"] > MAX_LESSONS:
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"errors": [
                            f"Слишком много пар: {summary['lessons']} "
                            f"(лимит {MAX_LESSONS})"]})
                self.crud.update_job(jid, input=summary)
        except BaseException:
            self.crud.remove_job(jid)
            raise

        self.workers.enqueue(jid)
        logger.info("create_job: поставлена задача jid=%s", jid)
        return jid

    # ---------- чтение ----------
    def get_or_404(self, job_id: str) -> dict[str, Any]:
        st = self.crud.get_job(job_id)
        if st is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                "Задача не найдена")
        return st

    def public_view(self, job_id: str, st: dict[str, Any]) -> dict[str, Any]:
        out = {k: v for k, v in st.items() if k not in ("pid", "trace")}
        out["id"] = job_id
        out["position"] = self.workers.position(job_id)
        return out

    # ---------- отмена / удаление ----------
    async def cancel(self, job_id: str) -> dict[str, Any]:
        st = self.get_or_404(job_id)
        if self.crud.is_terminal(st.get("status")):
            return self.public_view(job_id, st)
        await self.workers.cancel(job_id)
        st = self.crud.update_job(
            job_id, status="cancelled", finished=time.time(),
        )
        logger.info("cancel: задача jid=%s отменена", job_id)
        return self.public_view(job_id, st)

    async def delete(self, job_id: str) -> None:
        self.get_or_404(job_id)
        await self.cancel(job_id)
        self.crud.remove_job(job_id)
        logger.info("delete: задача jid=%s удалена", job_id)

    # ---------- результат ----------
    def result_path_or_409(self, job_id: str) -> Path:
        st = self.get_or_404(job_id)
        path = self.crud.job_dir(job_id) / "schedule.xlsx"
        if st.get("status") != "done" or not path.exists():
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Результат ещё не готов")
        return path

    # ---------- хелперы ----------
    @staticmethod
    async def _save_upload(up: UploadFile, dest: Path, max_upload: int) -> None:
        size = 0
        with open(dest, "wb") as f:
            while chunk := await up.read(CHUNK):
                size += len(chunk)
                if size > max_upload:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"Файл больше {max_upload // 2**20} МБ")
                f.write(chunk)

    @staticmethod
    async def _check_input(path: str) -> dict[str, int]:
        from data_loader import load_data
        teachers, groups, rooms, lessons = await run_in_threadpool(
            load_data, path, verbose=False,
        )
        return {"teachers": len(teachers), "groups": len(groups),
                "rooms": len(rooms), "lessons": len(lessons)}


generate_schedule_service: Final[GenerateScheduleService] = GenerateScheduleService()