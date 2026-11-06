from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core import generate_data, evaluate, run_ga
from core.cli import export_excel
from data_loader import DataError, load_data

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("timetable-api")

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", BASE_DIR / "storage")).resolve()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "30"))
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
DEFAULT_WORKERS = int(os.getenv("GA_WORKERS", str(max(1, (os.cpu_count() or 2) - 1))))
JOB_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
EXECUTOR = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS, thread_name_prefix="ga-job")

app = FastAPI(
    title="Timetable Generator API",
    version="1.0.0",
    description="Асинхронный API для составления расписания генетическим алгоритмом.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory registry: for production with multiple API replicas use Redis/DB + Celery/RQ.
jobs: dict[str, dict[str, Any]] = {}


class GenerateDemoRequest(BaseModel):
    n_teachers: int = Field(50, ge=1, le=5000)
    n_groups: int = Field(40, ge=1, le=5000)
    n_rooms: int = Field(30, ge=1, le=5000)
    pop_size: int = Field(60, ge=4, le=2000)
    generations: int = Field(300, ge=1, le=10000)
    elite: int = Field(4, ge=1, le=100)
    mutation_rate: float = Field(0.05, ge=0, le=1)
    workers: int = Field(DEFAULT_WORKERS, ge=1, le=128)
    seed: int = 42
    device: str = Field("cpu", pattern="^(cpu|numpy|cuda)$")


class JobAccepted(BaseModel):
    job_id: str
    status: str
    status_url: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_job() -> tuple[str, Path]:
    job_id = uuid.uuid4().hex
    work_dir = STORAGE_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=False)
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "created_at": utc_now(),
        "started_at": None,
        "finished_at": None,
        "score": None,
        "stats": None,
        "error": None,
        "warnings": [],
        "result_file": None,
    }
    return job_id, work_dir


def safe_extract_csv_zip(zip_path: Path, destination: Path) -> Path:
    required = {"преподаватели.csv", "группы.csv", "аудитории.csv", "нагрузка.csv"}
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        csv_members = [m for m in archive.infolist() if m.filename.lower().endswith(".csv")]
        found = set()
        for member in csv_members:
            name = Path(member.filename).name
            if name.lower() not in required:
                continue
            if member.is_dir():
                continue
            target = destination / name
            # Copy by basename only; never extract arbitrary archive paths.
            with archive.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            found.add(name.lower())
    missing = required - found
    if missing:
        raise ValueError("В ZIP отсутствуют CSV-файлы: " + ", ".join(sorted(missing)))
    return destination


def run_schedule_job(
    job_id: str,
    source_path: Path | None,
    params: dict[str, Any],
    demo: bool = False,
) -> None:
    """Синхронная CPU-bound задача. Запускается в отдельном потоке API."""
    record = jobs[job_id]
    work_dir = STORAGE_DIR / job_id
    try:
        record["status"] = "running"
        record["started_at"] = utc_now()

        if demo:
            teachers, groups, rooms, lessons = generate_data(
                n_teachers=params.pop("n_teachers"),
                n_groups=params.pop("n_groups"),
                n_rooms=params.pop("n_rooms"),
                seed=params.pop("seed", 42),
            )
            warnings = []
        else:
            assert source_path is not None
            input_path = source_path
            if source_path.suffix.lower() == ".zip":
                input_path = safe_extract_csv_zip(source_path, work_dir / "csv_data")
            teachers, groups, rooms, lessons = load_data(
                str(input_path), verbose=False
            )
            warnings = []

        started = datetime.now(timezone.utc)
        best, score = run_ga(
            lessons, teachers, groups, rooms,
            pop_size=params["pop_size"],
            generations=params["generations"],
            elite=params["elite"],
            mutation_rate=params["mutation_rate"],
            workers=params["workers"],
            seed=params.get("seed", 1),
            verbose=False,
            device=params["device"],
        )
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        _, stats = evaluate(best, lessons, teachers, groups, rooms)

        output = work_dir / "schedule.xlsx"
        export_excel(
            str(output), best, lessons, teachers, groups, rooms,
            score, stats, params=params, elapsed=elapsed,
        )
        record.update({
            "status": "completed",
            "finished_at": utc_now(),
            "score": float(score),
            "stats": stats,
            "warnings": warnings,
            "elapsed_seconds": round(elapsed, 3),
            "result_file": str(output),
            "data_summary": {
                "teachers": len(teachers),
                "groups": len(groups),
                "rooms": len(rooms),
                "lessons": len(lessons),
            },
        })
    except DataError as exc:
        record.update({
            "status": "failed",
            "finished_at": utc_now(),
            "error": {"type": "DataError", "details": exc.errors},
        })
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        record.update({
            "status": "failed",
            "finished_at": utc_now(),
            "error": {"type": type(exc).__name__, "details": str(exc)},
        })


async def dispatch_job(job_id: str, source_path: Path | None, params: dict, demo: bool = False):
    async with JOB_SEMAPHORE:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            EXECUTOR, run_schedule_job, job_id, source_path, params, demo
        )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "timetable-api"}


@app.post("/api/v1/jobs/upload", response_model=JobAccepted, status_code=202)
async def create_job_from_upload(
    file: UploadFile = File(...),
    pop_size: int = 60,
    generations: int = 300,
    elite: int = 4,
    mutation_rate: float = 0.05,
    workers: int = DEFAULT_WORKERS,
    seed: int = 1,
    device: str = "cpu",
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".xlsm", ".zip"}:
        raise HTTPException(415, "Поддерживаются .xlsx, .xlsm или ZIP с четырьмя CSV")
    if pop_size < 4 or generations < 1 or elite < 1 or elite >= pop_size:
        raise HTTPException(422, "Проверьте параметры pop_size, generations и elite")
    if not 0 <= mutation_rate <= 1 or workers < 1 or workers > 128:
        raise HTTPException(422, "Некорректные mutation_rate или workers")
    if device not in {"cpu", "numpy", "cuda"}:
        raise HTTPException(422, "device должен быть cpu, numpy или cuda")

    job_id, work_dir = new_job()
    saved = work_dir / f"input{suffix}"
    size = 0
    try:
        with saved.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"Файл превышает {MAX_UPLOAD_MB} MB")
                out.write(chunk)
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        jobs.pop(job_id, None)
        raise
    finally:
        await file.close()

    params = {
        "pop_size": pop_size, "generations": generations, "elite": elite,
        "mutation_rate": mutation_rate, "workers": workers,
        "seed": seed, "device": device,
    }
    asyncio.create_task(dispatch_job(job_id, saved, params))
    return JobAccepted(job_id=job_id, status="queued", status_url=f"/api/v1/jobs/{job_id}")


@app.post("/api/v1/jobs/demo", response_model=JobAccepted, status_code=202)
async def create_demo_job(request: GenerateDemoRequest):
    if request.elite >= request.pop_size:
        raise HTTPException(422, "elite должен быть меньше pop_size")
    job_id, _ = new_job()
    params = request.model_dump()
    asyncio.create_task(dispatch_job(job_id, None, params, demo=True))
    return JobAccepted(job_id=job_id, status="queued", status_url=f"/api/v1/jobs/{job_id}")


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str):
    record = jobs.get(job_id)
    if not record:
        raise HTTPException(404, "Задача не найдена")
    return {k: v for k, v in record.items() if k != "result_file"} | {
        "download_url": f"/api/v1/jobs/{job_id}/result"
        if record["status"] == "completed" else None
    }


@app.get("/api/v1/jobs/{job_id}/result")
async def download_result(job_id: str):
    record = jobs.get(job_id)
    if not record:
        raise HTTPException(404, "Задача не найдена")
    if record["status"] != "completed" or not record.get("result_file"):
        raise HTTPException(409, "Результат ещё не готов")
    path = Path(record["result_file"])
    if not path.is_file():
        raise HTTPException(404, "Файл результата не найден")
    return FileResponse(
        path, filename="schedule.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/v1/jobs")
async def list_jobs():
    return [
        {k: v for k, v in item.items() if k != "result_file"}
        for item in sorted(jobs.values(), key=lambda x: x["created_at"], reverse=True)
    ]


@app.on_event("shutdown")
async def shutdown_event():
    EXECUTOR.shutdown(wait=False, cancel_futures=True)
