"""
Хранилище задач на диске: jobs_data/<id>/{status.json, input.xlsx, schedule.xlsx}.

Состояние лежит в файлах, а не в памяти процесса, поэтому:
  * воркер (отдельный процесс) и API общаются без очередей и сокетов;
  * после перезапуска сервера результаты не теряются;
  * запись атомарная (tmp + os.replace) — читатель никогда не увидит
    наполовину записанный JSON.
У задачи в каждый момент один писатель (API до старта воркера, затем воркер).
"""
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

DATA_DIR = Path(os.environ.get("SCHEDULE_DATA", "jobs_data")).resolve()
TERMINAL = {"done", "failed", "cancelled"}
ACTIVE = {"queued", "running"}
_ID = re.compile(r"[0-9a-f]{32}")


def valid_id(job_id: str) -> bool:
    return bool(_ID.fullmatch(job_id or ""))


def job_dir(job_id: str, create: bool = False) -> Path:
    if not valid_id(job_id):            # защита от path traversal
        raise ValueError("bad job id")
    d = DATA_DIR / job_id
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def _status_path(job_id: str) -> Path:
    return job_dir(job_id) / "status.json"


def read(job_id: str):
    try:
        return json.loads(_status_path(job_id).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def mtime_ns(job_id: str) -> int:
    try:
        return _status_path(job_id).stat().st_mtime_ns
    except (OSError, ValueError):
        return 0


def _write(job_id: str, data: dict) -> None:
    p = _status_path(job_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)


def update(job_id: str, **fields) -> dict:
    data = read(job_id) or {}
    data.update(fields)
    data["updated"] = time.time()
    _write(job_id, data)
    return data


def create(params: dict, input_name, summary: dict) -> str:
    job_id = uuid.uuid4().hex
    job_dir(job_id, create=True)
    _write(job_id, {
        "status": "queued", "created": time.time(), "updated": time.time(),
        "params": params, "input_name": input_name, "input": summary,
        "progress": {"gen": 0, "total": params["generations"], "best": None},
        "history": [],
    })
    return job_id


def remove(job_id: str) -> None:
    shutil.rmtree(job_dir(job_id), ignore_errors=True)


def all_ids():
    if not DATA_DIR.exists():
        return []
    return [p.name for p in DATA_DIR.iterdir()
            if p.is_dir() and valid_id(p.name)]


def cleanup(ttl_seconds: float) -> int:
    """Удаляет завершённые задачи старше ttl. Возвращает число удалённых."""
    now, n = time.time(), 0
    for jid in all_ids():
        st = read(jid)
        if st is None:
            # осиротевшая папка без статуса
            if now - job_dir(jid).stat().st_mtime > ttl_seconds:
                remove(jid)
                n += 1
        elif st.get("status") in TERMINAL \
                and now - st.get("updated", now) > ttl_seconds:
            remove(jid)
            n += 1
    return n
