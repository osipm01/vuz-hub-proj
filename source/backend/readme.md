# VuzHub Backend — Микросервисная архитектура
 
# сборка
## Архитектура

| Сервис | Порт | БД | Описание |
|--------|------|-----|----------|
| `auth-service` | 8001 | `vuzhub_auth` | Аутентификация, пользователи, JWT |
| `study-service` | 8002 | `vuzhub_study` | Группы, предметы, расписание |
| `finance-service` | 8003 | `vuzhub_finance` | Долги, доп. услуги |
| `integration-service` | 8004 | `vuzhub_integration` | Внешние интеграции |

**Общий Redis** на порту 6379 для кэширования и межсервисного взаимодействия.

## Быстрый старт

### 1. Проверить Docker

```bash
docker --version
docker compose version
```

### 2. Запустить все сервисы

```bash
python run.py up
```

Это запустит:
- 4 контейнера PostgreSQL (по одному на каждый сервис)
- 1 контейнер Redis
- 4 контейнера с бэкенд-сервисами

### 3. Проверить статус

```bash
python run.py status
```

Или через Docker:
```bash
docker compose ps
```

### 4. Открыть API

- Auth: http://localhost:8001/docs
- Study: http://localhost:8002/docs
- Finance: http://localhost:8003/docs
- Integration: http://localhost:8004/docs

### 5. Посмотреть логи

```bash
python run.py logs auth-service
```

### 6. Остановить всё

```bash
python run.py down
```

## Управление

### Пересобрать образы

```bash
python run.py build
```

### Перезапустить конкретный сервис

```bash
python run.py restart study-service
```

### Запустить миграции

```bash
python run.py migrate auth-service
```

### Открыть shell в контейнере

```bash
python run.py shell finance-service
```

### Посмотреть статус БД

```bash
python run.py db integration-service
```

### Полная очистка (с удалением данных!)

```bash
python run.py clean
```

## Структура проекта

```
backend/
├── core/
│   ├── config.py          # Настройки (читает .env сервиса)
│   └── database.py        # SQLAlchemy engine + session
├── models/
│   ├── auth.py            # Модель User
│   ├── study.py           # Group, Subject, Schedule, UserSubject
│   ├── finance.py         # Debt, Dop
│   └── integration.py     # IntegrationLog, IntegrationToken
├── crud/
│   ├── auth/              # CRUD для auth
│   ├── study/             # CRUD для study
│   ├── finance/           # CRUD для finance
│   └── integration/       # CRUD для integration
├── services/
│   ├── auth/              # Бизнес-логика auth
│   ├── study/             # Бизнес-логика study
│   ├── finance/           # Бизнес-логика finance
│   └── integration/       # Бизнес-логика integration
├── schemas/
│   ├── auth/              # Pydantic схемы auth
│   ├── study/             # Pydantic схемы study
│   ├── finance/           # Pydantic схемы finance
│   └── integration/       # Pydantic схемы integration
├── routers/               # FastAPI роутеры
├── guards/                # Role guard, валидация токенов
├── migrations/            # Alembic миграции
├── .env.auth              # Конфиг auth-service
├── .env.study             # Конфиг study-service
├── .env.finance           # Конфиг finance-service
├── .env.integration       # Конфиг integration-service
├── docker-compose.yml     # Оркестрация
├── Dockerfile             # Образ для сервисов
└── run.py                 # CLI управление
```

## Переменные окружения

### .env.auth
```
SERVICE_NAME=auth-service
PORT=8001
DB_HOST=auth-db
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=admin
DB_NAME=vuzhub_auth
SECRET_JWT_KEY=qwert
REDIS_HOST=redis
REDIS_PORT=6379
```

### .env.study
```
SERVICE_NAME=study-service
PORT=8002
DB_HOST=study-db
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=admin
DB_NAME=vuzhub_study
REDIS_HOST=redis
REDIS_PORT=6379
```

### .env.finance
```
SERVICE_NAME=finance-service
PORT=8003
DB_HOST=finance-db
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=admin
DB_NAME=vuzhub_finance
REDIS_HOST=redis
REDIS_PORT=6379
```

### .env.integration
```
SERVICE_NAME=integration-service
PORT=8004
DB_HOST=integration-db
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=admin
DB_NAME=vuzhub_integration
REDIS_HOST=redis
REDIS_PORT=6379
```

## Разработка

### Локальный запуск (без Docker)

1. Поднять БД:
```bash
docker run -d --name auth-db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=vuzhub_auth -p 5432:5432 postgres:16-alpine
docker run -d --name study-db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=vuzhub_study -p 5433:5432 postgres:16-alpine
docker run -d --name finance-db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=vuzhub_finance -p 5434:5432 postgres:16-alpine
docker run -d --name integration-db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=vuzhub_integration -p 5435:5432 postgres:16-alpine
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

2. Запустить миграции:
```bash
set DB_NAME=vuzhub_auth& set DB_HOST=localhost
python -m alembic upgrade head
```

3. Запустить сервис:
```bash
set SERVICE_NAME=auth-service
set PORT=8001
set DB_NAME=vuzhub_auth
set DB_HOST=localhost
python -m uvicorn main:app --reload --port 8001
```

## Межсервисное взаимодействие

Сервисы общаются через:
- **HTTP/REST** — синхронные запросы
- **Redis** — кэширование и pub/sub события

Пример: `auth-service` проверяет группу через `study-service` по internal HTTP.

## Production

Для продакшена:
1. Сменить `SECRET_JWT_KEY` на случайную строку
2. Сменить пароли PostgreSQL
3. Включить HTTPS через nginx/reverse proxy
4. Настроить мониторинг (Prometheus + Grafana)
5. Настроить логирование (ELK/Graylog)
6. Настроить бэкапы PostgreSQL
