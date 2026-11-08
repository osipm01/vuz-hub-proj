DAYS = 5
SLOTS_PER_DAY = 6
TOTAL_SLOTS = DAYS * SLOTS_PER_DAY  # 30

DAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт"]

# Чётность недели пары
PARITY_BOTH, PARITY_ODD, PARITY_EVEN = 0, 1, 2
PARITY_WEEKS = {PARITY_BOTH: (0, 1), PARITY_ODD: (0,), PARITY_EVEN: (1,)}
PARITY_LABEL = {PARITY_BOTH: "Каждая", PARITY_ODD: "Нечётная",
                PARITY_EVEN: "Чётная"}
PARITY_SHORT = {PARITY_BOTH: "", PARITY_ODD: "[нечёт] ", PARITY_EVEN: "[чёт] "}

# Тип занятия: лекция может быть у нескольких групп сразу (поток),
# практика и лабораторная — только у одной группы
KIND_LECTURE, KIND_PRACTICE, KIND_LAB = "lecture", "practice", "lab"
KIND_LABEL = {KIND_LECTURE: "Лекция", KIND_PRACTICE: "Практика",
              KIND_LAB: "Лабораторная"}
KIND_SHORT = {KIND_LECTURE: "лек.", KIND_PRACTICE: "пр.", KIND_LAB: "лаб."}

# Ансамбли корпусов для тестовых данных (generate_data): корпус -> ансамбль.
# Идентификатор ансамбля = наименьший индекс корпуса в нём. Между корпусами
# одного ансамбля переход бесшовный (пары подряд допустимы), между разными
# ансамблями нужно окно не менее 1 слота.
SYNTH_ENSEMBLE = {0: 0, 1: 0, 2: 2, 3: 3, 4: 3}

# Веса штрафов (W_DIFF_BUILDING_ADJ_* — штраф за пары подряд в РАЗНЫХ АНСАМБЛЯХ)
W_CONFLICT_TEACHER = 1000
W_CONFLICT_GROUP = 1000
W_CONFLICT_ROOM = 1000
W_CAPACITY = 500
W_COMPUTER = 900            # пара требует компьютерный класс, а аудитория обычная
W_BUILDING_HARD = 800
W_DIFF_BUILDING_ADJ_T = 200
W_DIFF_BUILDING_ADJ_G = 200
W_GROUP_BUILDING_CHANGES = 400
W_PREF_TIME = 10
W_PREF_BUILDING = 15
W_GAP = 5                   # за каждый слот "окна" (любое окно)
W_GAP_BIG = 150             # за каждый лишний слот сверх допустимого окна в 1 слот
MAX_GAP = 1                 # допустимое окно между парами в день (в слотах)
