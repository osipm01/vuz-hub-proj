"""
FastAPI-приложение: загрузка данных -> очередь -> процесс-воркер -> Excel.

Запуск (из корня проекта, рядом с core/ и data_loader.py):
    uvicorn webapp.server:app --host 0.0.0.0 --port 8000

Важно: ОДИН процесс uvicorn (без --workers N). Очередь расчётов живёт в
этом процессе; параллелизм обеспечивают процессы-воркеры расчёта
(MAX_CONCURRENT_JOBS) и пул внутри каждого расчёта.
"""
import asyncio
import multiprocessing as mp
import os
import signal
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from webapp import jobstore as store
from webapp.worker import run_job

CPU = os.cpu_count() or 1
MAX_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "1"))   # GA сам грузит все ядра
MAX_QUEUE = int(os.environ.get("MAX_QUEUE", "20"))
MAX_UPLOAD = int(os.environ.get("MAX_UPLOAD_MB", "20")) * 1024 * 1024
MAX_LESSONS = int(os.environ.get("MAX_LESSONS", "20000"))
TTL = float(os.environ.get("JOB_TTL_HOURS", "24")) * 3600
STATIC = Path(__file__).parent / "static"


class State:
    queue: "asyncio.Queue[str]"
    waiting: list            # id задач в очереди (для позиции)
    procs: dict              # id -> Process
    cancelling: set


S = State()


# ------------------------------------------------------------
# управление процессами
# ------------------------------------------------------------
def _signal_group(proc, sig_name: str) -> None:
    sig = getattr(signal, sig_name, None)
    try:
        if hasattr(os, "killpg") and sig is not None:
            os.killpg(proc.pid, sig)          # pgid == pid после os.setsid()
        elif sig_name == "SIGKILL":
            proc.kill()
        else:
            proc.terminate()
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()                  # setsid ещё не успел выполниться
        except Exception:                     # noqa: BLE001
            pass


async def _kill(proc) -> None:
    if not proc.is_alive():
        return
    _signal_group(proc, "SIGTERM")
    for _ in range(20):                       # до 2 с на мягкое завершение
        if not proc.is_alive():
            return
        await asyncio.sleep(0.1)
    _signal_group(proc, "SIGKILL")
    for _ in range(30):
        if not proc.is_alive():
            return
        await asyncio.sleep(0.1)


async def _runner() -> None:
    """Берёт задачи из очереди и гоняет каждую в отдельном процессе."""
    ctx = mp.get_context("spawn")
    while True:
        jid = await S.queue.get()
        try:
            if jid in S.waiting:
                S.waiting.remove(jid)
            st = store.read(jid)
            if not st or st.get("status") != "queued":
                continue                      # отменена/удалена в очереди
            store.update(jid, status="running", started=time.time())
            proc = ctx.Process(target=run_job, args=(jid,),
                               name=f"job-{jid[:8]}")
            await asyncio.to_thread(proc.start)
            S.procs[jid] = proc
            while proc.is_alive():
                await asyncio.sleep(0.5)
            proc.join(0)
            S.procs.pop(jid, None)
            if jid in S.cancelling:
                continue                      # статус выставит обработчик отмены
            st = store.read(jid)
            if st and st.get("status") in store.ACTIVE:
                store.update(jid, status="failed", finished=time.time(),
                             error="Процесс расчёта завершился аварийно "
                                   f"(код {proc.exitcode}); возможно, не хватило памяти")
        except Exception as exc:              # noqa: BLE001
            try:
                store.update(jid, status="failed", error=f"{type(exc).__name__}: {exc}")
            except Exception:                 # noqa: BLE001
                pass
        finally:
            S.queue.task_done()


async def _janitor() -> None:
    while True:
        await asyncio.sleep(600)
        await asyncio.to_thread(store.cleanup, TTL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.DATA_DIR.mkdir(parents=True, exist_ok=True)
    S.queue, S.waiting, S.procs, S.cancelling = asyncio.Queue(), [], {}, set()
    # задачи, оборванные перезапуском сервера
    for jid in store.all_ids():
        st = store.read(jid)
        if st and st.get("status") in store.ACTIVE:
            store.update(jid, status="failed", finished=time.time(),
                         error="Сервер был перезапущен во время расчёта")
    tasks = [asyncio.create_task(_runner()) for _ in range(MAX_JOBS)]
    tasks.append(asyncio.create_task(_janitor()))
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        for proc in list(S.procs.values()):
            _signal_group(proc, "SIGKILL")


app = FastAPI(title="Составитель расписания", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)


# ------------------------------------------------------------
# вспомогательное
# ------------------------------------------------------------
def _public(jid: str, st: dict) -> dict:
    out = {k: v for k, v in st.items() if k not in ("pid", "trace")}
    out["id"] = jid
    out["position"] = S.waiting.index(jid) + 1 if jid in S.waiting else 0
    return out


def _get(jid: str) -> dict:
    st = store.read(jid) if store.valid_id(jid) else None
    if st is None:
        raise HTTPException(404, "Задача не найдена")
    return st


async def _save_upload(up: UploadFile, dest: Path) -> None:
    size = 0
    with open(dest, "wb") as f:
        while chunk := await up.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(
                    413, f"Файл больше {MAX_UPLOAD // 2**20} МБ")
            f.write(chunk)


def _check_input(path: str) -> dict:
    """Полная валидация данных (выполняется в потоке, не блокирует loop)."""
    from data_loader import load_data
    teachers, groups, rooms, lessons = load_data(path, verbose=False)
    return {"teachers": len(teachers), "groups": len(groups),
            "rooms": len(rooms), "lessons": len(lessons)}


# ------------------------------------------------------------
# API
# ------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"ok": True, "cpu": CPU, "queued": len(S.waiting),
            "running": len(S.procs), "max_jobs": MAX_JOBS}


@app.post("/api/jobs", status_code=202)
async def create_job(
    file: Optional[UploadFile] = File(None),
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
):
    if len(S.waiting) >= MAX_QUEUE:
        raise HTTPException(429, "Очередь переполнена, попробуйте позже")
    if elite >= pop:
        raise HTTPException(422, "elite должно быть меньше размера популяции")

    params = dict(pop=pop, generations=generations, mutation=mutation,
                  elite=elite, workers=min(workers, CPU), device=device,
                  seed=seed, teachers=teachers, groups=groups, rooms=rooms)

    has_file = file is not None and bool(file.filename)
    if has_file and not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(422, "Нужен файл .xlsx")

    jid = store.create(params, file.filename if has_file else None, {})
    try:
        if has_file:
            dest = store.job_dir(jid) / "input.xlsx"
            await _save_upload(file, dest)
            try:
                summary = await run_in_threadpool(_check_input, str(dest))
            except Exception as exc:          # DataError, битый zip и т.п.
                errors = getattr(exc, "errors", None) or \
                    [f"Не удалось прочитать файл: {exc}"]
                raise HTTPException(422, detail={"errors": errors})
            if summary["lessons"] > MAX_LESSONS:
                raise HTTPException(
                    422, detail={"errors": [
                        f"Слишком много пар: {summary['lessons']} "
                        f"(лимит {MAX_LESSONS})"]})
            store.update(jid, input=summary)
    except BaseException:
        store.remove(jid)
        raise

    S.waiting.append(jid)
    S.queue.put_nowait(jid)
    return {"id": jid}


@app.get("/api/jobs/{jid}")
async def job_status(jid: str):
    return _public(jid, _get(jid))


@app.get("/api/jobs/{jid}/events")
async def job_events(jid: str, request: Request):
    """Server-Sent Events: шлём статус только когда файл статуса изменился."""
    _get(jid)

    async def gen():
        last, idle = 0, 0
        while True:
            if await request.is_disconnected():
                return
            m = store.mtime_ns(jid)
            st = store.read(jid)
            if st is None:
                yield "data: {\"status\":\"gone\"}\n\n"
                return
            pos = S.waiting.index(jid) + 1 if jid in S.waiting else 0
            if m != last or (pos and idle % 4 == 0):
                last = m
                idle = 0
                import json
                yield f"data: {json.dumps(_public(jid, st), ensure_ascii=False)}\n\n"
                if st.get("status") in store.TERMINAL:
                    return
            idle += 1
            if idle % 30 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/jobs/{jid}/result")
async def job_result(jid: str):
    st = _get(jid)
    path = store.job_dir(jid) / "schedule.xlsx"
    if st.get("status") != "done" or not path.exists():
        raise HTTPException(409, "Результат ещё не готов")
    return FileResponse(
        path, filename="schedule.xlsx",
        media_type="application/vnd.openxmlformats-officedocument."
                   "spreadsheetml.sheet")


@app.post("/api/jobs/{jid}/cancel")
async def job_cancel(jid: str):
    st = _get(jid)
    status = st.get("status")
    if status in store.TERMINAL:
        return _public(jid, st)
    S.cancelling.add(jid)
    try:
        if jid in S.waiting:
            S.waiting.remove(jid)
        proc = S.procs.get(jid)
        if proc is not None:
            await _kill(proc)
        st = store.update(jid, status="cancelled", finished=time.time())
    finally:
        S.cancelling.discard(jid)
    return _public(jid, st)


@app.delete("/api/jobs/{jid}", status_code=204)
async def job_delete(jid: str):
    _get(jid)
    await job_cancel(jid)
    store.remove(jid)


@app.get("/api/template")
async def template():
    path = store.DATA_DIR / "template.xlsx"
    if not path.exists():
        from data_loader import make_template
        await run_in_threadpool(make_template, str(path))
    return FileResponse(path, filename="шаблон_данных.xlsx")


@app.exception_handler(HTTPException)
async def http_exc(_, exc: HTTPException):
    body = exc.detail if isinstance(exc.detail, dict) else {"error": exc.detail}
    return JSONResponse(body, status_code=exc.status_code)


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")
