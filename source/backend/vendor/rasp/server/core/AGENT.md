# Документация для ИИ-агента: составление расписания генетическим алгоритмом

---

## 1. Назначение системы

Программа составляет расписание занятий вуза (пары, группы, преподаватели, аудитории) **генетическим алгоритмом** (ГА). На вход — списки преподавателей, групп, аудиторий и пар; на выход — `schedule.xlsx` с расписанием, статистикой и списком нарушений.

Главная задача — минимизировать штраф (фитнес), складывающийся из **жёстких нарушений** (конфликты, нехватка мест, отсутствие компьютерного класса) и **мягких** (окна, смены корпусов, неучтённые предпочтения).

---

## 2. Структура проекта

```
project/
├── main.py            # точка входа
└── core/
    ├── __init__.py
    ├── constants.py   # дни, слоты, веса штрафов, типы пар
    ├── models.py      # dataclass-модели
    ├── ai.py          # генерация, фитнес, операторы ГА, run_ga
    └── cli.py         # argparse, экспорт в Excel
```

### Роли модулей

| Модуль | Ответственность |
|--------|-----------------|
| `constants.py` | Единственный источник истины по размерам (5 дней × 6 пар = 30 слотов), типам пар, весам штрафов, `MAX_GAP`. |
| `models.py` | `Teacher`, `Group`, `Room`, `Lesson`. `Lesson.weeks` — какие недели (нечёт/чёт) идут пары. |
| `ai.py` | `generate_data`, `evaluate`, `repair_*`, операторы ГА, `BatchEvaluator` (numpy/CuPy), `run_ga`. |
| `cli.py` | `parse_args`, `export_excel` (openpyxl), 6 листов Excel. |

---

## 3. Модель данных

### 3.1. Ключевые сущности

```python
Teacher(id, name, preferred_slots: dict[slot->вес], preferred_building, allowed_buildings)
Group(id, name, size)
Room(id, building, capacity, is_computer, name, building_name)
Lesson(id, teacher_id, group_id, extra_group_ids, length, needs_computer, parity, kind)
```

### 3.2. Особенности

- **Потоковые лекции.** `Lesson.group_ids` = `(group_id,) + extra_group_ids`. Пара занимает **все** группы одновременно; конфликт проверяется по каждой.
- **Чётность недели.** `parity ∈ {BOTH, ODD, EVEN}`. `Lesson.weeks` → `(0,1)`, `(0,)` или `(1,)`.
- **Длина пары.** `length` — обычно 1. `BatchEvaluator` поддерживает только `length == 1`; иначе автоматический откат на CPU.

### 3.3. Индивид (расписание)

```python
individual = [(slot, room_id), ...]   # по одному кортежу на Lesson, порядок = порядок lessons
```

`slot ∈ [0, 30)`, `room_id` — индекс в `rooms`. Длина индивида = `len(lessons)`.

---

## 4. Фитнес-функция (`evaluate`)

Считает штраф (чем больше — тем лучше; старт с 0). Возвращает `(score, stats)`.

| Компонент | Вес | Условие |
|-----------|-----|---------|
| Конфликт преподавателя | −1000 | Две пары одного преподавателя в один слот одной недели |
| Конфликт группы | −1000 | То же для любой группы пары |
| Конфликт аудитории | −1000 | Две пары в одной аудитории в один слот одной недели |
| Малая вместимость | −500 | `room.capacity < Σ group.size` |
| Нет компьютерного класса | −900 | `needs_computer and not room.is_computer` |
| Недопустимый корпус | −800 | `room.building ∉ teacher.allowed_buildings` |
| Смена корпуса подряд (T) | −200 | Соседние пары преподавателя в разных корпусах без перерыва |
| Смена корпуса подряд (G) | −200 | То же для группы |
| Лишняя смена корпуса за день (G) | −400 | Больше одной смены у группы в день |
| Окно у T/G | −5 × gap | Любой разрыв между парами в течение дня |
| Большое окно | −150 × (gap − MAX_GAP) | Разрыв больше допустимого |
| Предпочтение по времени | +10 × weight | Слот в `teacher.preferred_slots` |
| Предпочтение по корпусу | +15 | Совпадение с `preferred_building` |

**Симметрия.** `evaluate` (скалярный, в воркерах) и `BatchEvaluator.fitness` (векторный, numpy/CuPy) дают идентичный результат — это проверяется тестом.

---

## 5. Генетический алгоритм (`run_ga`)

### 5.1. Параметры

| Аргумент | Смысл | По умолчанию |
|----------|-------|--------------|
| `pop_size` | Размер популяции | 150 |
| `generations` | Число поколений | 500 |
| `elite` | Число элитных особей | 6 |
| `mutation_rate` | Вероятность мутации гена | 0.03 |
| `workers` | Процессов | `os.cpu_count()` |
| `device` | `cpu` / `cuda` / `numpy` | `cpu` |

### 5.2. Жизненный цикл

```
random_individual → repair_conflicts → repair_group_buildings → evaluate
       ↓
  [поколение]
       ├── элитизм (top-elite переносятся как есть)
       ├── турнирный отбор родителей (k=5)
       ├── crossover (одна точка) → 2 потомка
       ├── mutate (0.6 — слот, 0.4 — аудитория)
       ├── repair_conflicts + repair_group_buildings
       └── evaluate (в воркере или батчем на GPU)
       ↓
  лучший индивид
```

### 5.3. Ремонтные операторы

- **`repair_conflicts`** — жадно устраняет конфликты: сначала пробует остаться в том же слоте, потом меняет аудиторию, потом слот (сортировка слотов по «стоимости окон»). Второй проход — уплотнение (убирает окна > `MAX_GAP`).
- **`repair_group_buildings`** — для каждой группы/дня выбирает «главный» корпус (где больше всего пар и есть подходящие аудитории для всех пар дня) и переносит остальные пары туда, не создавая конфликтов аудиторий.

### 5.4. GPU-оценка (`BatchEvaluator`)

- Реализация одна для `cupy` (CUDA) и `numpy`.
- Ограничение: все пары длиной 1 слот.
- Векторизует: конфликты по неделям, вместимость, компьютерные классы, предпочтения, окна/смены корпусов у T и G.
- Используется, когда `device != cpu` и `make_evaluator` вернул не `None`.

---

## 6. Экспорт в Excel (`export_excel`)

Открывается `Workbook`, создаются листы:

| Лист | Содержимое |
|------|------------|
| **Сводка** | Общие метрики (пары, лекции/практики/лабы, фитнес, конфликты, окна, предпочтения, время расчёта, параметры запуска). |
| **По корпусам** | Агрегаты по зданиям + отдельная таблица занятости аудиторий-слотов по дням (нечёт/чёт). |
| **Все пары** | Плоская таблица всех пар с проблемами (красная заливка — нарушения, синяя — компьютерные пары). |
| **По преподавателям** | Сетка 5×6: строки — преподаватели, столбцы — слоты. |
| **По группам** | Сетка 5×6: строки — группы, столбцы — слоты. |
| **Нарушения** | Строки только с непустым `problems_of`. |

`problems_of(lesson, slot, rid)` пересчитывает конфликты независимо от `evaluate` — чтобы в отчёте были явные формулировки («Конфликт группы», «Нужен компьютерный класс» и т.п.).

---

## 7. Интерфейс командной строки

```bash
python main.py \
    --teachers 800 --groups 400 --rooms 200 \
    --pop 150 --generations 500 --mutation 0.03 --elite 6 \
    --computer-share 0.15 --lecture-share 0.35 --alt-share 0.25 \
    --workers 8 --device cpu \
    --out schedule.xlsx
```

| Флаг | Смысл |
|------|-------|
| `--teachers/--groups/--rooms` | Размер синтетических данных |
| `--pop`, `--generations`, `--mutation`, `--elite` | Параметры ГА |
| `--computer-share` | Доля пар, требующих компьютерный класс |
| `--lecture-share` | Доля лекций (могут быть потоковыми) |
| `--alt-share` | Доля пар только в одну чётность |
| `--workers` | Процессов (`1` — без параллельности) |
| `--device` | `cpu` / `cuda` / `numpy` |
| `--data` | Путь к `.xlsx` или папке CSV (реальные данные) |
| `--out` | Куда сохранить результат |

---

## 8. Пайплайн запуска (псевдокод)

```python
args = parse_args()
teachers, groups, rooms, lessons = generate_data(...)  # или load_data(args.data)
t0 = time.time()
best, score = run_ga(
    lessons, teachers, groups, rooms,
    pop_size=args.pop, generations=args.generations,
    elite=args.elite, mutation_rate=args.mutation,
    workers=args.workers, device=args.device,
)
_, stats = evaluate(best, lessons, teachers, groups, rooms)
export_excel(args.out, best, lessons, teachers, groups, rooms,
             score, stats, params=vars(args), elapsed=time.time() - t0)
```

---

## 9. Правила для ИИ-агента

### 9.1. Что можно менять без риска

- **Веса штрафов** в `constants.py` — влияют только на «строгость» критериев. Не меняют структуру данных.
- **`MAX_GAP`** — допустимый размер окна. Учтите: логика `gap > MAX_GAP` влияет и в `evaluate`, и в `BatchEvaluator`.
- **Параметры `run_ga`** (`pop_size`, `generations`, `mutation_rate`, `elite`).
- **Шаблоны вывода** в `export_excel` (колонки, заливки, названия листов).

### 9.2. Что менять осторожно

- **`Lesson`/`Group`/`Room`/`Teacher`** — изменения полей каскадно влияют на `evaluate`, `BatchEvaluator`, `export_excel`. При добавлении поля:
  1. Обновить `generate_data`.
  2. Обновить скалярный `evaluate`.
  3. Обновить `BatchEvaluator.__init__` и `fitness`.
  4. Обновить `export_excel`.
- **Число слотов/дней** (`DAYS`, `SLOTS_PER_DAY`) — перепроверить `slot_day/slot_time`, все `% TOTAL_SLOTS`, `// SLOTS_PER_DAY` в векторизованном коде.
- **`length > 1`** — сломает `BatchEvaluator` (там жёсткое `slot` без `range`). Либо оставлять `device=cpu`, либо переписывать `BatchEvaluator`.

### 9.3. Что нельзя ломать

- **Симметрия `evaluate` и `BatchEvaluator`.** Любое изменение штрафа — в обоих местах. Проверять тестом на маленькой популяции.
- **Picklability** `Lesson/Teacher/Group/Room` — иначе `multiprocessing.Pool` на `spawn` (Windows/macOS) упадёт.
- **`if __name__ == "__main__":`** в точке входа — иначе спавн-процессы рекурсивно запустят `main`.
- **Совместимость `individual[i]` ↔ `lessons[i]`** по порядку. Если сортируете/фильтруете — синхронно.

### 9.4. Частые ошибки

| Симптом | Причина | Что делать |
|---------|---------|-----------|
| `KeyError` в `_CTX["suitable"]` | Воркер не вызвал `_init_worker`, или `lessons` не совпадают по длине | Убедиться, что `Pool(initializer=_init_worker, initargs=...)` получил те же данные |
| Расхождение `evaluate` и GPU | Изменили веса только в одном месте | Синхронизировать константы и пересчитать оба |
| Зависание на `spawn` | Нет `if __name__ == "__main__"` | Добавить в `main.py` |
| Падение на `length > 1` с `--device cuda` | `BatchEvaluator` не поддерживает | `device=cpu` или переписать |
| `FileNotFoundError` в Excel | Нет прав / нет папки | Проверить `--out` |

### 9.5. Как расширять

- **Новый критерий** (например, «не более N пар в день у группы»):
  1. Константа веса в `constants.py`.
  2. Проверка в `evaluate` (секция 6/7).
  3. Аналогичная проверка в `BatchEvaluator.fitness` (секция 4).
  4. Строка статистики в `stats` и в «Сводке» Excel.
  5. При необходимости — в `repair_*`.

- **Новый тип занятия**: добавить константу `KIND_*`, обновить `KIND_LABEL`/`KIND_SHORT`, обновить `generate_data` (если нужно), `export_excel`.

- **Новая форма отчёта**: новый лист в `export_excel`, не трогая существующие.

---

## 10. Мини-пример

```python
from core import generate_data, run_ga, evaluate
from core.cli import export_excel
import time

teachers, groups, rooms, lessons = generate_data(
    n_teachers=80, n_groups=40, n_rooms=30, seed=42,
)
t0 = time.time()
best, score = run_ga(
    lessons, teachers, groups, rooms,
    pop_size=60, generations=200, elite=4,
    mutation_rate=0.05, workers=4, device="cpu",
)
_, stats = evaluate(best, lessons, teachers, groups, rooms)
export_excel("demo.xlsx", best, lessons, teachers, groups, rooms,
             score, stats, elapsed=time.time() - t0)
print("fitness:", score, "conflicts:", stats["conflicts"])
```

---

## 11. Технические требования

- Python 3.9+
- `openpyxl` — Excel
- `numpy` — векторизованный фитнес (опционально)
- `cupy-cuda12x` — GPU (опционально)
- `multiprocessing` — стандартная библиотека (на Windows/macOS — `spawn`)

Установка:

```bash
pip install openpyxl numpy
pip install cupy-cuda12x    # только если нужна CUDA
```

---
