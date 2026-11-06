"""
Воркер одного расчёта. Запускается как ОТДЕЛЬНЫЙ процесс (spawn) на каждую
задачу — это даёт:
  * изоляцию: падение/OOM расчёта не роняет API;
  * возможность жёсткой отмены (убиваем всю группу процессов);
  * свой multiprocessing.Pool внутри run_ga (в daemonic-процессах пулы
    создавать нельзя, поэтому ProcessPoolExecutor здесь не подходит).
Прогресс пишется в status.json не чаще раза в 0.4 с.
"""
import os
import time
import traceback

from webapp import jobstore as store

HISTORY_MAX = 300


def run_job(job_id: str) -> None:
    try:
        os.setsid()            # свой process group: cancel убьёт и пул воркеров
    except (AttributeError, OSError):
        pass                   # Windows

    t0 = time.time()
    try:
        job = store.read(job_id)
        p = job["params"]
        store.update(job_id, pid=os.getpid(), started=t0)

        # тяжёлые импорты — уже внутри процесса расчёта
        from core import evaluate, generate_data, run_ga
        from core.cli import export_excel
        from data_loader import DataError, load_data

        in_path = store.job_dir(job_id) / "input.xlsx"
        if in_path.exists():
            teachers, groups, rooms, lessons = load_data(
                str(in_path), verbose=False)
        else:
            teachers, groups, rooms, lessons = generate_data(
                n_teachers=p["teachers"], n_groups=p["groups"],
                n_rooms=p["rooms"], seed=p["seed"])

        store.update(job_id, input={
            "teachers": len(teachers), "groups": len(groups),
            "rooms": len(rooms), "lessons": len(lessons)})

        history, last = [], [0.0]

        def progress(gen, total, best):
            now = time.time()
            if gen not in (0, total - 1) and now - last[0] < 0.4:
                return
            last[0] = now
            history.append([gen, best])
            if len(history) > HISTORY_MAX:      # прореживаем вдвое
                del history[1::2]
            store.update(job_id, progress={
                "gen": gen + 1, "total": total, "best": best,
                "elapsed": now - t0}, history=history)

        best, score = run_ga(
            lessons, teachers, groups, rooms,
            pop_size=p["pop"], generations=p["generations"],
            elite=p["elite"], mutation_rate=p["mutation"],
            workers=p["workers"], seed=p["seed"], verbose=False,
            device=p["device"], progress=progress)

        store.update(job_id, stage="export")
        _, stats = evaluate(best, lessons, teachers, groups, rooms)
        elapsed = time.time() - t0
        export_excel(
            str(store.job_dir(job_id) / "schedule.xlsx"), best, lessons,
            teachers, groups, rooms, score, stats,
            params={k: str(v) for k, v in p.items()}, elapsed=elapsed)

        store.update(job_id, status="done", stage=None, finished=time.time(),
                     result={"score": score, "stats": stats,
                             "elapsed": round(elapsed, 1)})

    except Exception as exc:                      # noqa: BLE001
        errors = None
        try:
            from data_loader import DataError
            if isinstance(exc, DataError):
                errors = exc.errors
        except Exception:                         # noqa: BLE001
            pass
        store.update(job_id, status="failed", finished=time.time(),
                     error=("Ошибки в данных" if errors else
                            f"{type(exc).__name__}: {exc}"),
                     errors=errors,
                     trace=None if errors else traceback.format_exc()[-2000:])
