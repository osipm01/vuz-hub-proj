"""Эндпоинты работы с задачами генерации расписания."""
import asyncio
import json
import logging
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

from services.generate_schedule_service import generate_schedule_service
from services.worker_service import worker_service
from webapp import jobstore as store

logger: Final[logging.Logger] = logging.getLogger(__name__)
router: Final[APIRouter] = APIRouter(prefix="/api", tags=["jobs"])

# конфиг-константы передаём в сервис из роутера (чтобы не дублировать env в сервисе)
import os

CPU: Final[int] = os.cpu_count() or 1
MAX_QUEUE: Final[int] = int(os.environ.get("MAX_QUEUE", "20"))
MAX_UPLOAD: Final[int] = int(os.environ.get("MAX_UPLOAD_MB", "20")) * 1024 * 1024


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "cpu": CPU,
            "queued": worker_service.queued_count,
            "running": worker_service.running_count}


@router.post("/jobs", status_code=202)
async def create_job(
    file: UploadFile | None = File(None),
    pop: int = Form(100, ge=10, le=1000),
    generations: int = Form(300, ge=1, le=5000),
    mutation: float = Form(0.03, ge=0.001, le=0.5),
    elite: int = Form(4, ge=1, le=50),
    workers: int = Form(CPU, ge=1, le=256),
    device: str = Form("cpu", pattern="^(cpu|cuda|numpy)$"),
    seed: int = Form(1),
    teachers: int = Form(50, ge=1, le=2000),
    groups: int = Form(40, ge=1, le=1000),
    rooms: int = Form(30, ge=1, le=500),
) -> dict[str, str]:
    jid = await generate_schedule_service.create_job(
        file=file, pop=pop, generations=generations, mutation=mutation,
        elite=elite, workers=workers, device=device, seed=seed,
        teachers=teachers, groups=groups, rooms=rooms,
        max_queue=MAX_QUEUE, max_upload=MAX_UPLOAD, cpu=CPU,
    )
    return {"id": jid}


@router.get("/jobs/{jid}")
async def job_status(jid: str) -> dict[str, Any]:
    st = generate_schedule_service.get_or_404(jid)
    return generate_schedule_service.public_view(jid, st)


@router.get("/jobs/{jid}/events")
async def job_events(jid: str, request: Request) -> StreamingResponse:
    generate_schedule_service.get_or_404(jid)

    async def gen():
        last, idle = 0, 0
        while True:
            if await request.is_disconnected():
                return
            m = jobstore_mtime(jid)
            st = generate_schedule_service.get_or_404(jid) \
                if _job_exists(jid) else None
            if st is None:
                yield 'data: {"status":"gone"}\n\n'
                return
            pos = worker_service.position(jid)
            if m != last or (pos and idle % 4 == 0):
                last = m
                idle = 0
                yield f"data: {json.dumps(generate_schedule_service.public_view(jid, st), ensure_ascii=False)}\n\n"
                if st.get("status") in {"done", "failed", "cancelled"}:
                    return
            idle += 1
            if idle % 30 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def jobstore_mtime(jid: str) -> int:
    return generate_schedule_service.crud.get_mtime_ns(jid)


def _job_exists(jid: str) -> bool:
    return generate_schedule_service.crud.get_job(jid) is not None


@router.get("/jobs/{jid}/result")
async def job_result(jid: str) -> FileResponse:
    path = generate_schedule_service.result_path_or_409(jid)
    return FileResponse(
        path, filename="schedule.xlsx",
        media_type="application/vnd.openxmlformats-officedocument."
                   "spreadsheetml.sheet",
    )


@router.post("/jobs/{jid}/cancel")
async def job_cancel(jid: str) -> dict[str, Any]:
    return await generate_schedule_service.cancel(jid)


@router.delete("/jobs/{jid}", status_code=204)
async def job_delete(jid: str) -> None:
    await generate_schedule_service.delete(jid)


@router.get("/template")
async def template() -> FileResponse:
    from pathlib import Path
    path = store.DATA_DIR / "template.xlsx"
    if not path.exists():
        from data_loader import make_template
        await run_in_threadpool(make_template, str(path))
    return FileResponse(path, filename="шаблон_данных.xlsx")