<template>
  <label class="checkbox-label" :class="{ 'checkbox-label--disabled': disabled }">
    <input
      type="checkbox"
      :checked="modelValue"
      :value="value"
      :disabled="disabled"
      class="custom-checkbox"
      @change="onChange"
    />
    <span class="checkbox-text">
      <slot>{{ label }}</slot>
    </span>
  </label>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  modelValue: boolean | number[] | string[]
  value?: number | string
  label?: string
  disabled?: boolean
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean | number[] | string[]]
}>()

const onChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  const checked = target.checked

  // Если есть value — работаем как с массивом (checkbox group)
  if (props.value !== undefined) {
    const current = Array.isArray(props.modelValue) ? [...props.modelValue] : []
    const idx = current.indexOf(props.value)
    if (checked && idx === -1) current.push(props.value)
    if (!checked && idx !== -1) current.splice(idx, 1)
    emit('update:modelValue', current)
    return
  }

  // Обычный boolean checkbox
  emit('update:modelValue', checked)
}
</script>

<style scoped>
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  cursor: pointer;
  user-select: none;
}

.checkbox-label--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.custom-checkbox {
  width: 18px;
  height: 18px;
  accent-color: #2ec4b6;
  cursor: pointer;
  flex-shrink: 0;
}

.checkbox-text {
  line-height: 1.2;
}
</style>