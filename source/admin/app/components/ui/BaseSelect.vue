<template>
  <div class="input-field-group">
    <label v-if="label" :for="selectId" class="field-label">{{ label }}</label>
    <select
      :id="selectId"
      :value="modelValue"
      :disabled="disabled"
      class="custom-input custom-select"
      @change="onChange"
    >
      <option v-if="placeholder" :value="null" disabled>{{ placeholder }}</option>
      <slot />
    </select>
  </div>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: string | number | null
  label?: string
  placeholder?: string
  disabled?: boolean
  id?: string
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number | null]
}>()

const generatedId = useId()
const selectId = computed(() => props.id || `select-${generatedId}`)

const onChange = (event: Event) => {
  const target = event.target as HTMLSelectElement
  const raw = target.value
  // Пробуем преобразовать в число, если это возможно
  const num = Number(raw)
  emit('update:modelValue', raw !== '' && !isNaN(num) ? num : raw)
}
</script>

<style scoped>
.input-field-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
}

.custom-input {
  width: 100%;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #333333;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
}

.custom-select {
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23555' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right 12px center;
  background-size: 16px;
  padding-right: 38px;
  cursor: pointer;
}

.custom-input:disabled {
  background: rgba(255, 255, 255, 0.5);
  cursor: not-allowed;
}
</style>