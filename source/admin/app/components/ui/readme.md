# 📘 Документация UI-компонентов

Библиотека переиспользуемых компонентов для админ-панели. Все компоненты находятся в `components/ui/` и доступны глобально без префикса `Ui`.

---

## 📑 Содержание

1. [BaseInput](#baseinput)
2. [BaseTextarea](#basetextarea)
3. [BaseSelect](#baseselect)
4. [BaseCheckbox](#basecheckbox)
5. [BaseButton](#basebutton)
6. [BaseLink](#baselink)
7. [BaseBackLink](#basebacklink)
8. [BaseFormField](#baseformfield)
9. [useAsyncAction](#useasyncaction)
10. [Соглашения и стили](#соглашения-и-стили)

---

## BaseInput

Текстовый инпут с лейблом, подсказкой и состоянием ошибки. Поддерживает `text`, `password`, `email`, `number`, `url` и другие нативные типы.

### Импорт

```vue
<!-- Автоматически доступен глобально -->
<BaseInput v-model="value" label="Имя" />
```

### Props

| Prop | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `modelValue` | `string \| number \| null` | — | Значение (v-model) |
| `label` | `string` | — | Подпись над полем |
| `type` | `string` | `'text'` | HTML тип инпута |
| `placeholder` | `string` | — | Плейсхолдер |
| `disabled` | `boolean` | `false` | Блокировка |
| `required` | `boolean` | `false` | HTML `required` |
| `hint` | `string` | — | Подсказка под полем |
| `error` | `string` | — | Текст ошибки под полем |
| `min` | `number \| string` | — | Для `type="number"` |
| `max` | `number \| string` | — | Для `type="number"` |
| `step` | `number \| string` | — | Для `type="number"` |
| `id` | `string` | авто | HTML `id` (генерируется через `useId`) |

### Events

| Event | Payload | Описание |
|-------|---------|----------|
| `update:modelValue` | `string \| number \| null` | Изменение значения |
| `blur` | `FocusEvent` | Потеря фокуса |
| `focus` | `FocusEvent` | Получение фокуса |
| `enter` | — | Нажат Enter |

### Примеры

**Текстовое поле:**

```vue
<BaseInput
  v-model="form.username"
  label="Имя пользователя"
  placeholder="Введите логин"
  :disabled="isProcessing"
  required
/>
```

**Поле пароля:**

```vue
<BaseInput
  v-model="form.password"
  type="password"
  label="Пароль"
  placeholder="••••••••"
/>
```

**Числовое поле:**

```vue
<BaseInput
  v-model="newMediaId"
  type="number"
  label="ID медиафайла"
  :min="1"
  placeholder="ID"
/>
```

**С ошибкой и подсказкой:**

```vue
<BaseInput
  v-model="form.email"
  label="Email"
  type="email"
  hint="Мы не передаём email третьим лицам"
  :error="emailError"
/>
```

---

## BaseTextarea

Многострочное текстовое поле.

### Props

| Prop | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `modelValue` | `string` | — | Значение (v-model) |
| `label` | `string` | — | Подпись |
| `placeholder` | `string` | — | Плейсхолдер |
| `disabled` | `boolean` | `false` | Блокировка |
| `required` | `boolean` | `false` | HTML `required` |
| `hint` | `string` | — | Подсказка |
| `rows` | `number` | `4` | Кол-во строк |
| `id` | `string` | авто | HTML `id` |

### Events

| Event | Payload |
|-------|---------|
| `update:modelValue` | `string` |

### Пример

```vue
<BaseTextarea
  v-model="form.description"
  label="Описание"
  placeholder="Введите описание фильма"
  :rows="6"
  :disabled="isProcessing"
  required
/>
```

> ⚠️ `resize: vertical` включён по умолчанию — пользователь может тянуть за нижний угол.

---

## BaseSelect

Выпадающий список. Автоматически преобразует числовые значения в `number` и наоборот.

### Props

| Prop | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `modelValue` | `string \| number \| null` | — | Значение (v-model) |
| `label` | `string` | — | Подпись |
| `placeholder` | `string` | — | Опция-заглушка (disabled) |
| `disabled` | `boolean` | `false` | Блокировка |
| `id` | `string` | авто | HTML `id` |

### Events

| Event | Payload |
|-------|---------|
| `update:modelValue` | `string \| number \| null` |

### Слоты

| Слот | Описание |
|------|----------|
| `default` | `<option>` элементы |

### Примеры

**Простой селект:**

```vue
<BaseSelect v-model="form.role" label="Роль">
  <option value="user">User</option>
  <option value="admin">Admin</option>
</BaseSelect>
```

**Селект с числовыми значениями (id категории):**

```vue
<BaseSelect
  v-model="selectedCategoryId"
  label="Категория"
>
  <option :value="null">Все категории</option>
  <option
    v-for="cat in categories"
    :key="cat.id"
    :value="cat.id"
  >
    {{ cat.name }}
  </option>
</BaseSelect>
```

> ✅ `v-model` вернёт `null` или `number` — не строку. Это удобно для API-запросов.

---

## BaseCheckbox

Чекбокс с двумя режимами работы:

1. **Одиночный** (`modelValue: boolean`) — обычный вкл/выкл.
2. **Групповой** (`modelValue: number[] \| string[]`, задан `value`) — массив выбранных значений.

### Props

| Prop | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `modelValue` | `boolean \| number[] \| string[]` | — | Значение (v-model) |
| `value` | `number \| string` | — | Значение элемента (для группового режима) |
| `label` | `string` | — | Текст рядом с чекбоксом |
| `disabled` | `boolean` | `false` | Блокировка |

### Events

| Event | Payload |
|-------|---------|
| `update:modelValue` | `boolean \| number[] \| string[]` |

### Слоты

| Слот | Описание |
|------|----------|
| `default` | Заменяет текст `label` |

### Примеры

**Одиночный чекбокс:**

```vue
<BaseCheckbox
  v-model="form.is_active"
  label="Активен"
/>
```

**Групповой чекбокс (мультивыбор категорий):**

```vue
<div class="checkbox-grid">
  <BaseCheckbox
    v-for="category in categories"
    :key="category.id"
    v-model="form.category_ids"
    :value="category.id"
    :label="category.name"
    :disabled="isProcessing"
  />
</div>
```

> В `form.category_ids` хранится массив `number[]`.

**С кастомным слотом:**

```vue
<BaseCheckbox v-model="form.agree">
  Я согласен с <NuxtLink to="/terms">условиями</NuxtLink>
</BaseCheckbox>
```

---

## BaseButton

Кнопка с 5 вариантами стиля, размерами и встроенным индикатором загрузки.

### Props

| Prop | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `label` | `string` | — | Текст кнопки |
| `loadingText` | `string` | — | Текст при `loading=true` |
| `variant` | `'success' \| 'danger' \| 'primary' \| 'secondary' \| 'warning'` | `'primary'` | Стиль |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | Размер |
| `nativeType` | `'button' \| 'submit' \| 'reset'` | `'button'` | HTML тип |
| `disabled` | `boolean` | `false` | Блокировка |
| `loading` | `boolean` | `false` | Показать спиннер + блокировка |

### Events

| Event | Payload | Описание |
|-------|---------|----------|
| `click` | `MouseEvent` | Клик |

### Слоты

| Слот | Описание |
|------|----------|
| `default` | Содержимое кнопки (если не задан `label`) |

### Примеры

**Основные варианты:**

```vue
<BaseButton variant="success">Создать</BaseButton>
<BaseButton variant="danger">Удалить</BaseButton>
<BaseButton variant="primary">Редактировать</BaseButton>
<BaseButton variant="secondary">Отмена</BaseButton>
<BaseButton variant="warning">Отвязать</BaseButton>
```

**С загрузкой:**

```vue
<BaseButton
  variant="success"
  :loading="isProcessing"
  loading-text="Создание..."
  native-type="submit"
>
  Создать пользователя
</BaseButton>
```

**Маленькая кнопка в списке:**

```vue
<BaseButton
  variant="danger"
  size="sm"
  :loading="isProcessing"
  @click="deleteUser(user.id)"
>
  Удалить
</BaseButton>
```

**Только иконка/текст через слот:**

```vue
<BaseButton variant="secondary" @click="toggle">
  ⚙️ Настройки
</BaseButton>
```

---

## BaseLink

Ссылка `<NuxtLink>`, стилизованная как кнопка. Всегда используйте её вместо `<NuxtLink class="btn-action">`.

### Props

| Prop | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `to` | `string` | — | Куда ведёт ссылка (**обязательно**) |
| `label` | `string` | — | Текст ссылки |
| `variant` | `'success' \| 'danger' \| 'primary' \| 'secondary' \| 'warning'` | `'secondary'` | Стиль |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | Размер |

### Слоты

| Слот | Описание |
|------|----------|
| `default` | Содержимое ссылки |

### Примеры

**Кнопка «Отмена»:**

```vue
<BaseLink to="/users" variant="secondary">
  Отмена
</BaseLink>
```

**Кнопка «Редактировать» в списке:**

```vue
<BaseLink
  :to="`/users/${user.id}`"
  variant="primary"
  size="sm"
>
  Редактировать
</BaseLink>
```

**Кнопка создания:**

```vue
<BaseLink to="/users/create" variant="success">
  + Создать пользователя
</BaseLink>
```

---

## BaseBackLink

Стандартная ссылка «← Назад» с навигационным отступом.

### Props

| Prop | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `to` | `string` | — | Куда ведёт (**обязательно**) |
| `label` | `string` | `'← Назад'` | Текст |

### Слоты

| Слот | Описание |
|------|----------|
| `default` | Заменяет текст |

### Примеры

```vue
<BaseBackLink to="/users" />
<!-- → «← Назад» -->

<BaseBackLink to="/media/categories" label="← К списку категорий" />

<BaseBackLink to="/media/movies">
  ← Вернуться к фильмам
</BaseBackLink>
```

---

## BaseFormField

Обёртка для любого поля (в т.ч. кастомного), обеспечивающая единый стиль лейбла, подсказки и ошибки.

### Props

| Prop | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `label` | `string` | — | Подпись |
| `hint` | `string` | — | Подсказка |
| `error` | `string` | — | Ошибка |
| `id` | `string` | авто | HTML `id` (для связи с `<label for>`) |

### Слоты

| Слот | Описание |
|------|----------|
| `default` | Содержимое поля |

### Пример

```vue
<BaseFormField label="Категории" hint="Выберите одну или несколько">
  <div class="checkbox-grid">
    <BaseCheckbox
      v-for="cat in categories"
      :key="cat.id"
      v-model="form.category_ids"
      :value="cat.id"
      :label="cat.name"
    />
  </div>
</BaseFormField>
```

---

## useAsyncAction

Композабл для обработки асинхронных действий: управляет `loading`, `error` и автоматически показывает toast-уведомления.

### Сигнатура

```ts
useAsyncAction(
  action: (...args) => Promise<any>,
  options?: {
    toast?: {
      successMessage?: string | ((result) => string)
      errorMessage?: string | ((error) => string)
      silent?: boolean
    }
    onSuccess?: (result) => void
    onError?: (error) => void
  }
): {
  isProcessing: Ref<boolean>
  error: Ref<string | null>
  execute: (...args) => Promise<result | undefined>
}
```

### Возвращает

| Поле | Тип | Описание |
|------|-----|----------|
| `isProcessing` | `Ref<boolean>` | `true` во время выполнения |
| `error` | `Ref<string \| null>` | Текст ошибки (автоматически извлекается из `e.data.detail`) |
| `execute` | `(...args) => Promise` | Запускает действие |

### Пример 1. Простое создание

```ts
const { isProcessing, error, execute } = useAsyncAction(
  () => adminUserService.createUser(createForm),
  {
    toast: {
      successMessage: () => `Пользователь ${createForm.username} создан`,
      errorMessage: (e) => e?.data?.detail || `Ошибка ${e?.status}`,
    },
    onSuccess: () => router.push('/users'),
  }
)

const handleSubmit = () => execute().catch(() => {})
```

### Пример 2. Действие с аргументом (удаление)

```ts
const { execute: executeDelete } = useAsyncAction(
  (id: number) => adminUserService.deleteUser(id),
  {
    toast: {
      successMessage: 'Пользователь удалён',
      errorMessage: (e) => `Ошибка ${e?.status || ''}`,
    },
    onSuccess: () => refresh(),
  }
)

const deleteUser = async (id: number) => {
  if (!confirm('Удалить?')) return
  await executeDelete(id).catch(() => {})
}
```

### Пример 3. Без toast (`silent`)

```ts
const { execute } = useAsyncAction(
  () => someService.doStuff(),
  { toast: { silent: true } }
)
```

### Рекомендации

- Всегда используйте `try/catch` вокруг `execute()`, либо `.catch(() => {})`, т.к. композабл **пробрасывает** ошибку дальше.
- Для сложных форм, где toast не нужен — используйте `silent: true` и показывайте ошибки через `error` в шаблоне.
- `errorMessage` можно задать функцией — удобно, когда текст зависит от ответа API.

---

## Соглашения и стили

### Префиксы

| Префикс | Назначение | Пример |
|---------|-----------|--------|
| `Base*` | Базовые UI-компоненты | `BaseInput`, `BaseButton` |
| `GalssPanel` | Панель-обёртка (стеклянный стиль) | `<GalssPanel>` |
| `BaseForm` | Обёртка формы | `<BaseForm>` |

### Цветовая палитра кнопок

| Variant | Цвет | Использование |
|---------|------|---------------|
| `success` | `#2ec4b6` (бирюзовый) | Создать, сохранить |
| `danger` | `#e71d36` (красный) | Удалить |
| `primary` | `#0077aa` (синий) | Редактировать |
| `secondary` | Полупрозрачный белый | Отмена, назад |
| `warning` | `#ff9f1c` (оранжевый) | Отвязать, вторичные действия |

### Размеры

| Size | Padding | Font | Использование |
|------|---------|------|---------------|
| `sm` | 6px 12px | 13px | В списках, таблицах |
| `md` | 12px 24px | 14px | Формы, основные действия |

### Типовой layout страницы

```vue
<template>
  <GalssPanel>
    <BaseBackLink to="/users" />

    <BaseForm>
      <div class="form-content">
        <div class="form-header">
          <h1 class="page-title">Заголовок</h1>
        </div>

        <form @submit.prevent="handleSubmit" class="form-section">
          <BaseInput v-model="form.field" label="Поле" />

          <div class="action-bar">
            <BaseButton
              native-type="submit"
              variant="success"
              :loading="isProcessing"
              loading-text="Сохранение..."
            >
              Сохранить
            </BaseButton>
            <BaseLink to="/users" variant="secondary">Отмена</BaseLink>
          </div>
        </form>

        <div v-if="error" class="error-state">{{ error }}</div>
      </div>
    </BaseForm>
  </GalssPanel>
</template>
```

### CSS-классы (shared)

Эти классы используются во всех страницах — вынесите их в `assets/css/main.css`:

```css
.form-content { display: flex; flex-direction: column; gap: 24px; }
.form-header { display: flex; justify-content: space-between; align-items: center; }
.page-title { color: #fff; font-size: 24px; font-weight: 600; margin: 0; }
.form-section { display: flex; flex-direction: column; gap: 20px; }
.action-bar { margin-top: 8px; display: flex; gap: 12px; align-items: center; }
.form-divider { border: 0; height: 1px; background: rgba(255,255,255,.15); margin: 8px 0; }
.checkbox-grid { display: flex; flex-wrap: wrap; gap: 12px 20px; }
.loading-state { color: #fff; padding: 20px 0; text-align: center; }
.error-state {
  color: #ff6b6b;
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(255,107,107,.1);
  border: 1px solid rgba(255,107,107,.3);
  font-size: 14px;
  text-align: center;
}
.empty-state-text {
  color: rgba(255,255,255,.5);
  font-style: italic;
  font-size: 14px;
  text-align: center;
  padding: 20px 0;
}
```

---

## 🎯 Чек-лист при создании новой страницы

- [ ] Обернуть в `<GalssPanel>`
- [ ] Добавить `<BaseBackLink>` сверху
- [ ] Обернуть контент в `<BaseForm>`
- [ ] Использовать `<BaseInput>` / `<BaseTextarea>` / `<BaseSelect>` / `<BaseCheckbox>`
- [ ] Кнопки — только `<BaseButton>` и `<BaseLink>`
- [ ] Асинхронные действия — через `useAsyncAction`
- [ ] Ошибки и loading — из `useAsyncAction`, не дублировать вручную

---

## 📁 Структура проекта

```
components/
├── GalssPanel.vue
├── BaseForm.vue
└── ui/
    ├── BaseInput.vue
    ├── BaseTextarea.vue
    ├── BaseSelect.vue
    ├── BaseCheckbox.vue
    ├── BaseButton.vue
    ├── BaseLink.vue
    ├── BaseBackLink.vue
    └── BaseFormField.vue

composables/
└── useAsyncAction.ts
```
