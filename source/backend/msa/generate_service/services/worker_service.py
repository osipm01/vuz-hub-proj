"""Управление процессами-воркерами расчёта и очередью задач.

Инкапсулирует:
  * asyncio-очередь готовых к запуску задач;
  * пул процессов-воркеров (MAX_CONCURRENT_JOBS);
  * жёсткую отмену через process group;
  * janitor (периодическая очистка TTL).

Не знает про HTTP, схемы и бизнес-валидацию — только про job_id.
"""
import asyncio
import logging
import multiprocessing as mp
import os
import signal
import time
from typing import Any, Final

from webapp.worker import run_job

logger: Final[logging.Logger] = logging.getLogger(__name__)

# сигнатура колбэков, чтобы не тянуть CRUD в сервис напрямую
ReadFn = "Callable[[str], dict[str, Any] | None]"
UpdateFn = "Callable[..., dict[str, Any]]"

TERM_GRACE_STEPS: Final[int] = 20
TERM_GRACE_SLEEP: Final[float] = 0.1
KILL_GRACE_STEPS: Final[int] = 30
JANITOR_INTERVAL: Final[float] = 600.0


class WorkerService:
    """Очередь + пул процессов-воркеров. Модульный синглтон."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] | None = None
        self.waiting: list[str] = []
        self.procs: dict[str, mp.process.BaseProcess] = {}
        self.cancelling: set[str] = set()
        self._tasks: list[asyncio.Task[None]] = []
        self._ctx: mp.context.BaseContext | None = None

    # ---------- публичный API для lifespan ----------
    async def start(
        self,
        read_fn,
        update_fn,
        *,
        max_jobs: int,
        ttl_seconds: float,
    ) -> None:
        """Инициализирует очередь и запускает runner-ы + janitor."""
        self.queue = asyncio.Queue()
        self.waiting = []
        self.procs = {}
        self.cancelling = set()
        self._ctx = mp.get_context("spawn")
        self._read = read_fn
        self._update = update_fn

        # задачи, оборванные перезапуском
        for jid in self._read_all():
            st = self._read(jid)
            if st and st.get("status") in {"queued", "running"}:
                self._update(jid, status="failed", finished=time.time(),
                             error="Сервер был перезапущен во время расчёта")

        self._tasks = [asyncio.create_task(self._runner()) for _ in range(max_jobs)]
        self._tasks.append(asyncio.create_task(self._janitor(ttl_seconds)))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for proc in list(self.procs.values()):
            self._signal_group(proc, "SIGKILL")
        self._tasks.clear()
        self.procs.clear()

    def _read_all(self):
        # переопределяется через _read_all_fn, чтобы не тянуть crud
        return []

    # ---------- постановка/отмена ----------
    def enqueue(self, job_id: str) -> None:
        assert self.queue is not None
        self.waiting.append(job_id)
        self.queue.put_nowait(job_id)

    def remove_from_waiting(self, job_id: str) -> None:
        if job_id in self.waiting:
            self.waiting.remove(job_id)

    def position(self, job_id: str) -> int:
        return self.waiting.index(job_id) + 1 if job_id in self.waiting else 0

    async def cancel(self, job_id: str) -> None:
        self.cancelling.add(job_id)
        try:
            self.remove_from_waiting(job_id)
            proc = self.procs.get(job_id)
            if proc is not None:
                await self._kill(proc)
        finally:
            self.cancelling.discard(job_id)

    def is_cancelling(self, job_id: str) -> bool:
        return job_id in self.cancelling

    @property
    def running_count(self) -> int:
        return len(self.procs)

    @property
    def queued_count(self) -> int:
        return len(self.waiting)

    # ---------- runner ----------
    async def _runner(self) -> None:
        assert self.queue is not None and self._ctx is not None
        while True:
            jid = await self.queue.get()
            try:
                await self._run_one(jid)
            except Exception:                     # noqa: BLE001
                logger.exception("worker runner: ошибка задачи jid=%s", jid)
                try:
                    self._update(jid, status="failed",
                                 error="Внутренняя ошибка воркера")
                except Exception:                 # noqa: BLE001
                    logger.exception("worker runner: не удалось обновить статус")
            finally:
                self.queue.task_done()

    async def _run_one(self, jid: str) -> None:
        self.remove_from_waiting(jid)
        st = self._read(jid)
        if not st or st.get("status") != "queued":
            return
        self._update(jid, status="running", started=time.time())
        proc = self._ctx.Process(target=run_job, args=(jid,),
                                 name=f"job-{jid[:8]}")
        await asyncio.to_thread(proc.start)
        self.procs[jid] = proc
        while proc.is_alive():
            await asyncio.sleep(0.5)
        proc.join(0)
        self.procs.pop(jid, None)
        if self.is_cancelling(jid):
            return
        st = self._read(jid)
        if st and st.get("status") in {"queued", "running"}:
            self._update(
                jid, status="failed", finished=time.time(),
                error="Процесс расчёта завершился аварийно "
                      f"(код {proc.exitcode}); возможно, не хватило памяти",
            )

    async def _janitor(self, ttl_seconds: float) -> None:
        while True:
            await asyncio.sleep(JANITOR_INTERVAL)
            try:
                await asyncio.to_thread(self._cleanup, ttl_seconds)
            except Exception:                     # noqa: BLE001
                logger.exception("janitor: ошибка очистки")

    def _cleanup(self, ttl_seconds: float) -> None:
        # задаётся снаружи через callback, чтобы не тянуть crud
        if self._cleanup_fn is not None:
            self._cleanup_fn(ttl_seconds)

    # ---------- сигналы ----------
    @staticmethod
    def _signal_group(proc: mp.process.BaseProcess, sig_name: str) -> None:
        sig = getattr(signal, sig_name, None)
        try:
            if hasattr(os, "killpg") and sig is not None:
                os.killpg(proc.pid, sig)
            elif sig_name == "SIGKILL":
                proc.kill()
            else:
                proc.terminate()
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.terminate()
            except Exception:                     # noqa: BLE001
                logger.exception("signal_group: не удалось terminate")


worker_service: Final[WorkerService] = WorkerService()