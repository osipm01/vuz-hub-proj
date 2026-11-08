# Timetable Generator — FastAPI backend

Backend оборачивает существующее ядро генетического алгоритма, не меняя его fitness,
модели и Excel-экспорт.

## Структура

```text
timetable_fastapi_backend/
├── main.py
├── data_loader.py
├── requirements.txt
└── core/
    ├── __init__.py
    ├── ai.py
    ├── cli.py
    ├── constants.py
    └── models.py
```

## Установка и запуск

Python 3.10+:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload
```

Документация Swagger: http://127.0.0.1:8000/docs

## API

- `GET /health` — проверка доступности.
- `POST /api/v1/jobs/upload` — загрузить Excel `.xlsx`/`.xlsm` либо ZIP с CSV
  `Преподаватели.csv`, `Группы.csv`, `Аудитории.csv`, `Нагрузка.csv`.
- `POST /api/v1/jobs/demo` — создать демонстрационную задачу на синтетических данных.
- `GET /api/v1/jobs/{job_id}` — статус, метрики и ссылка на результат.
- `GET /api/v1/jobs/{job_id}/result` — скачать `schedule.xlsx`.
- `GET /api/v1/jobs` — список задач текущего процесса API.

Пример запуска демо:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/demo \
  -H "Content-Type: application/json" \
  -d '{"n_teachers":30,"n_groups":20,"n_rooms":20,"pop_size":40,"generations":100,"elite":4,"workers":4}'
```

Пример загрузки:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/upload \
  -F "file=@data.xlsx" \
  -F "pop_size=60" -F "generations=300" -F "workers=4"
```

В ответе `202 Accepted` вернётся `job_id`. Клиент опрашивает
`GET /api/v1/jobs/{job_id}` до `completed` и скачивает файл по `download_url`.

## Как устроена асинхронность

HTTP-обработчик только сохраняет входной файл и ставит задачу в очередь исполнения.
CPU-bound `run_ga()` выполняется вне event loop в ограниченном `ThreadPoolExecutor`.
Сам `run_ga()` использует свой `multiprocessing.Pool` для распараллеливания
генетических операций по параметру `workers`. Поэтому HTTP-сервер остаётся отзывчивым,
а число одновременно выполняемых расписаний ограничено `MAX_CONCURRENT_JOBS`.

Переменные окружения:
- `MAX_UPLOAD_MB=30`
- `MAX_CONCURRENT_JOBS=2`
- `GA_WORKERS` — число процессов генетического алгоритма
- `STORAGE_DIR` — директория хранения файлов
- `LOG_LEVEL=INFO`

## Важные ограничения

1. Реестр задач хранится в памяти: после перезапуска API статусы исчезают.
   Для нескольких реплик/production замените его на PostgreSQL + Redis/Celery или RQ.
2. Отмена выполняющейся задачи намеренно не реализована: `run_ga()` сейчас не
   предоставляет безопасного механизма остановки извне.
3. Для CUDA используйте совместимую с вашей CUDA версию CuPy отдельно.
4. Запускайте один Uvicorn worker для этого in-memory варианта (`--workers 1`).
   Внутренние GA workers — отдельный параметр запроса.
5. Не запускайте `uvicorn --reload` в production.
