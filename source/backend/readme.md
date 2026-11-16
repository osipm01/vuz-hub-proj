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

---

# API Documentation для фронтенда

> **Base URL:** `http://localhost:8001` (monolith) или порты сервисов 8001–8004 (микросервисы)  
> **Swagger UI:** `/docs` на каждом порту  
> **CORS:** временно разрешены все (`*`), позже будет ограничено

## 🔐 Аутентификация

### Как передавать токен
Фронтенд может использовать один из трёх способов (выбираешь тот, который удобнее):

| Способ | Заголовок/Cookie | Тип аутентификации |
|---|---|---|
| **Bearer** | `Authorization: Bearer <token>` | `client` (по умолчанию) |
| **Header** | `x-auth-token: <token>` + `x-auth-type: client` | `client` |
| **Cookie** | `access_token=<token>` | `client` (по умолчанию) |

Для ботов: `x-auth-type: BOT` + `x-bot-token: <token>`  
Для интеграций: `x-auth-type: INTEGRATION` + `x-integration-key: <key>`

### Роли
| Роль | Описание |
|------|----------|
| `user` | Обычный пользователь |
| `admin` | Администратор (управление пользователями) |
| `dispatcher` | Диспетчер |

### JWT payload
```json
{
  "sub": "<user_id>",
  "role": "<role>",
  "exp": <unix_timestamp>,
  "iat": <unix_timestamp>
}
```

### Токены
| Токен | TTL |
|-------|-----|
| Access token | 30 минут |
| Refresh token | 7 дней |

---

## 1. Auth (`/auth`)

### `POST /auth/register`
Регистрация нового пользователя.  
**Ответ:** `200 OK` — `TokenResponse`

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "string (min 6 chars)",
  "full_name": "string | optional"
}
```

**Response:**
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "user_id": 1,
  "role": "user",
  "is_new_user": true
}
```

---

### `POST /auth/login`
Вход по email + password.  
**Ответ:** `200 OK` — `TokenResponse`

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "string (min 6 chars)"
}
```

---

### `POST /auth/logout`
Выход (очищает куки). Требует аутентификации.  
**Ответ:** `204 No Content`

---

### `POST /auth/login/social`
Вход через соцсеть.  
**Ответ:** `200 OK` — `TokenResponse`

**Request Body:**
```json
{
  "link_type": "vk | max_id | tg_id",
  "social_id": 123456,
  "email": "user@example.com | optional"
}
```

---

### `POST /auth/login/vk`
Быстрый вход через VK.  
**Query params:**
| Param | Type | Required |
|-------|------|----------|
| `vk_id` | int | Yes |
| `email` | string | No |

---

### `POST /auth/login/telegram`
Быстрый вход через Telegram.  
**Query params:**
| Param | Type | Required |
|-------|------|----------|
| `telegram_id` | int | Yes |
| `email` | string | No |

---

### `POST /auth/login/max`
Быстрый вход через MAX.  
**Query params:**
| Param | Type | Required |
|-------|------|----------|
| `max_id` | int | Yes |
| `email` | string | No |

---

## 2. Users (`/users`)

> ⚠️ Маршруты с `/me` — требуют аутентификации. Admin-маршруты — роль `admin` (`CLIENT`).

### `GET /users/me`
Профиль текущего пользователя. Требует аутентификации.  
**Ответ:** `200 OK` — `UserRead`

---

### `GET /users/`
Список всех пользователей. Только `admin`.  
**Query params:**
| Param | Type | Default | Constraints |
|-------|------|---------|-------------|
| `skip` | int | 0 | >= 0 |
| `limit` | int | 100 | 1–1000 |
| `group_id` | int | — | optional |

**Response:** `list[UserRead]`

---

### `GET /users/{user_id}`
Пользователь по ID. Только `admin`.  
**Response:** `UserRead`

---

### `GET /users/by-email`
Поиск по email. Только `admin`.  
**Query params:**
| Param | Type | Required |
|-------|------|----------|
| `email` | string | Yes |

**Response:** `UserRead`

---

### `POST /users/`
Создать пользователя. Только `admin`.  
**Ответ:** `201 Created` — `UserRead`

**Request Body:**
```json
{
  "email": "user@example.com",
  "name": "string",
  "password": "string | optional",
  "role": "user | admin | dispatcher | optional",
  "group_id": 1 | optional,
  "telegram_id": 123 | optional,
  "VK_id": 456 | optional,
  "MAX_id": 789 | optional
}
```

---

### `PUT /users/{user_id}`
Обновить пользователя. Только `admin`.  
**Response:** `UserRead`

**Request Body:**
```json
{
  "name": "string | optional",
  "email": "user@example.com | optional",
  "group_id": 1 | optional
}
```

---

### `PATCH /users/{user_id}/role`
Изменить роль. Только `admin`.  
**Response:** `UserRead`

**Request Body:**
```json
{
  "role": "user | admin | dispatcher"
}
```

---

### `DELETE /users/{user_id}`
Удалить пользователя. Только `admin`.  
**Ответ:** `204 No Content`

---

### `GET /users/{user_id}/social`
Соц. ссылки пользователя. Только `admin`.  
**Response:** `SocialLinksResponse`

```json
{
  "user_id": 1,
  "links": [
    { "link_type": "vk", "social_id": 123456 }
  ]
}
```

---

### `POST /users/{user_id}/social/link`
Привязать соц. сеть. Только `admin`.  
**Response:** `UserRead`

**Request Body:**
```json
{
  "link_type": "vk | max_id | tg_id",
  "social_id": 123456
}
```

---

### `POST /users/{user_id}/social/unlink`
Отвязать соц. сеть. Только `admin`.  
**Query params:**
| Param | Type |
|-------|------|
| `link_type` | `vk | max_id | tg_id` |

**Response:** `UserRead`

---

## 3. Groups (`/groups`) — без auth

### `GET /groups/`
Список групп.  
**Query params:** `skip` (0), `limit` (100).  
**Response:** `list[GroupRead]`

---

### `GET /groups/{group_id}`
Группа по ID.  
**Response:** `GroupRead`

---

### `GET /groups/by-name`
Поиск по имени.  
**Query params:** `name` (string)  
**Response:** `GroupRead`

---

### `POST /groups/`
Создать группу.  
**Ответ:** `201 Created` — `GroupRead`

**Request Body:**
```json
{
  "name": "СТУ-123"
}
```

---

### `PUT /groups/{group_id}`
Обновить группу.  
**Response:** `GroupRead`

**Request Body:**
```json
{
  "name": "СТУ-123 | optional"
}
```

---

### `DELETE /groups/{group_id}`
Удалить группу.  
**Ответ:** `204 No Content`

---

## 4. Subjects (`/subjects`) — без auth

### `GET /subjects/`
Список предметов.  
**Query params:** `skip` (0), `limit` (100).  
**Response:** `list[SubjectRead]`

---

### `GET /subjects/{subject_id}`
Предмет по ID.  
**Response:** `SubjectRead`

---

### `GET /subjects/by-name`
Поиск по имени.  
**Query params:** `name` (string)  
**Response:** `SubjectRead`

---

### `POST /subjects/`
Создать предмет.  
**Ответ:** `201 Created` — `SubjectRead`

**Request Body:**
```json
{
  "name": "Математика"
}
```

---

### `PUT /subjects/{subject_id}`
Обновить предмет.  
**Response:** `SubjectRead`

**Request Body:**
```json
{
  "name": "Математика | optional"
}
```

---

### `DELETE /subjects/{subject_id}`
Удалить предмет.  
**Ответ:** `204 No Content`

---

## 5. Schedules (`/schedules`) — без auth

### `GET /schedules/`
Расписание.  
**Query params:**
| Param | Type | Default |
|-------|------|---------|
| `skip` | int | 0 |
| `limit` | int | 100 |
| `group_id` | int | optional |
| `subject_id` | int | optional |
| `weekday` | int | optional (0–6) |

**Response:** `list[ScheduleRead]`

---

### `GET /schedules/{schedule_id}`
Расписание по ID.  
**Response:** `ScheduleRead`

---

### `POST /schedules/`
Создать запись расписания.  
**Ответ:** `201 Created` — `ScheduleRead`

**Request Body:**
```json
{
  "group_id": 1,
  "subject_id": 1,
  "weekday": 1,
  "start_time": "2024-01-15T09:00:00",
  "classroom": "A-301 | optional"
}
```

---

### `PUT /schedules/{schedule_id}`
Обновить запись расписания.  
**Response:** `ScheduleRead`

**Request Body:** (все поля optional)
```json
{
  "group_id": 1 | optional,
  "subject_id": 1 | optional,
  "weekday": 1 | optional,
  "start_time": "2024-01-15T09:00:00" | optional,
  "classroom": "A-301 | optional"
}
```

---

### `DELETE /schedules/{schedule_id}`
Удалить запись расписания.  
**Ответ:** `204 No Content`

---

## 6. Debts (`/debts`) — без auth

### `GET /debts/`
Список долгов.  
**Query params:**
| Param | Type | Default |
|-------|------|---------|
| `skip` | int | 0 |
| `limit` | int | 100 |
| `user_id` | int | optional |
| `subject_id` | int | optional |
| `is_resolved` | bool | optional |

**Response:** `list[DebtRead]`

---

### `GET /debts/{debt_id}`
Долг по ID.  
**Response:** `DebtRead`

---

### `POST /debts/`
Создать долг.  
**Ответ:** `201 Created` — `DebtRead`

**Request Body:**
```json
{
  "user_id": 1,
  "subject_id": 1,
  "description": "Не сдал экзамен"
}
```

---

### `PUT /debts/{debt_id}`
Обновить долг.  
**Response:** `DebtRead`

**Request Body:**
```json
{
  "subject_id": 1 | optional,
  "description": "string | optional",
  "is_resolved": false | optional
}
```

---

### `PATCH /debts/{debt_id}/resolve`
Отметить долг как погашенный.  
**Response:** `DebtRead`

---

### `DELETE /debts/{debt_id}`
Удалить долг.  
**Ответ:** `204 No Content`

---

## 7. Dops (`/dops`) — без auth

### `GET /dops/`
Список доп. услуг.  
**Query params:** `skip` (0), `limit` (100), `user_id` (optional)  
**Response:** `list[DopRead]`

---

### `GET /dops/{dop_id}`
Доп. услуга по ID.  
**Response:** `DopRead`

---

### `POST /dops/`
Создать доп. услугу.  
**Ответ:** `201 Created` — `DopRead`

**Request Body:**
```json
{
  "user_id": 1,
  "organization_name": "ООО Ромашка"
}
```

---

### `PUT /dops/{dop_id}`
Обновить доп. услугу.  
**Response:** `DopRead`

**Request Body:**
```json
{
  "organization_name": "string | optional"
}
```

---

### `DELETE /dops/{dop_id}`
Удалить доп. услугу.  
**Ответ:** `204 No Content`

---

## 8. User-Subjects (`/user-subjects`) — без auth

### `GET /user-subjects/`
Список привязок пользователей к предметам.  
**Query params:** `skip` (0), `limit` (100), `user_id` (optional), `subject_id` (optional)  
**Response:** `list[UserSubjectRead]`

---

### `GET /user-subjects/{user_id}/{subject_id}`
Привязка по composite key.  
**Response:** `UserSubjectRead`

---

### `POST /user-subjects/`
Создать привязку.  
**Ответ:** `201 Created` — `UserSubjectRead`

**Request Body:**
```json
{
  "user_id": 1,
  "subject_id": 1
}
```

---

### `DELETE /user-subjects/{user_id}/{subject_id}`
Удалить привязку.  
**Ответ:** `204 No Content`

---

## 📦 DTO Reference

### TokenResponse
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "user_id": 1,
  "role": "user",
  "is_new_user": true
}
```

### UserRead
```json
{
  "id": 1,
  "name": "Иванов Иван",
  "email": "user@example.com",
  "group_id": 1 | null,
  "role": "user",
  "created_at": "2024-01-15T10:00:00"
}
```

### GroupRead
```json
{
  "id": 1,
  "name": "СТУ-123"
}
```

### SubjectRead
```json
{
  "id": 1,
  "name": "Математика"
}
```

### ScheduleRead
```json
{
  "id": 1,
  "group_id": 1,
  "subject_id": 1,
  "weekday": 1,
  "start_time": "2024-01-15T09:00:00",
  "classroom": "A-301 | null"
}
```

### DebtRead
```json
{
  "id": 1,
  "user_id": 1,
  "subject_id": 1,
  "description": "Не сдал экзамен",
  "is_resolved": false
}
```

### DopRead
```json
{
  "id": 1,
  "user_id": 1,
  "organization_name": "ООО Ромашка"
}
```

### UserSubjectRead
```json
{
  "user_id": 1,
  "subject_id": 1
}
```

### SocialLinksResponse
```json
{
  "user_id": 1,
  "links": [
    { "link_type": "vk", "social_id": 123456 },
    { "link_type": "tg_id", "social_id": 789012 }
  ]
}
```

---

## 🗺 Роуты по сервисам

| Сервис | Порт | Роуты |
|--------|------|-------|
| **Monolith** | 8001 | Все роуты |
| **auth-service** | 8001 | `/auth`, `/users` |
| **study-service** | 8002 | `/groups`, `/schedules`, `/subjects`, `/user-subjects` |
| **finance-service** | 8003 | `/debts`, `/dops` |
| **integration-service** | 8004 | `/integrations` |

---

## 🗄 Database Models

### User (`users`)
| Column | Type | Description |
|--------|------|-------------|
| `id` | int | PK |
| `name` | string | Display name |
| `email` | string | Login, unique |
| `group_id` | int | FK → groups.id |
| `hashed_password` | string | BCrypt hash |
| `created_at` | datetime | Registration time |
| `role` | string | user/admin/dispatcher |
| `telegram_id` | bigint | Unique, nullable |
| `VK_id` | bigint | Unique, nullable |
| `MAX_id` | int | Unique, nullable |

### Group (`groups`)
| Column | Type | Description |
|--------|------|-------------|
| `id` | int | PK |
| `name` | string | Unique |
| `created_at` | datetime | -- |

### Subject (`subjects`)
| Column | Type | Description |
|--------|------|-------------|
| `id` | int | PK |
| `name` | string | Unique |
| `created_at` | datetime | -- |

### Schedule (`schedules`)
| Column | Type | Description |
|--------|------|-------------|
| `id` | int | PK |
| `group_id` | int | FK → groups (CASCADE DELETE) |
| `subject_id` | int | FK → subjects (CASCADE DELETE) |
| `weekday` | int | 0=Monday, 6=Sunday |
| `start_time` | datetime | -- |
| `classroom` | string | Nullable |

### Debt (`debts`)
| Column | Type | Description |
|--------|------|-------------|
| `id` | int | PK |
| `user_id` | int | FK → users (CASCADE DELETE) |
| `subject_id` | int | FK → subjects (CASCADE DELETE) |
| `description` | string | -- |
| `is_resolved` | bool | Default: false |
| `created_at` | datetime | -- |

### Dop (`dop`)
| Column | Type | Description |
|--------|------|-------------|
| `id` | int | PK |
| `user_id` | int | FK → users (CASCADE DELETE) |
| `organization_name` | string | -- |

### UserSubject (`user_subjects`) — composite PK
| Column | Type | Description |
|--------|------|-------------|
| `user_id` | int | PK, FK → users (CASCADE DELETE) |
| `subject_id` | int | PK, FK → subjects (CASCADE DELETE) |

---

## 🛠 Enums

### UserRole
- `user`
- `admin`
- `dispatcher`

### SocialNetworkLinkType
- `vk`
- `max_id`
- `tg_id`

Для продакшена:
1. Сменить `SECRET_JWT_KEY` на случайную строку
2. Сменить пароли PostgreSQL
3. Включить HTTPS через nginx/reverse proxy
4. Настроить мониторинг (Prometheus + Grafana)
5. Настроить логирование (ELK/Graylog)
6. Настроить бэкапы PostgreSQL
