<template>
  <div class="input-field-group">
    <label v-if="label" :for="inputId" class="field-label">{{ label }}</label>
    <input
      :id="inputId"
      :value="modelValue"
      :type="type"
      :placeholder="placeholder"
      :disabled="disabled"
      :required="required"
      :min="min"
      :max="max"
      :step="step"
      class="custom-input"
      @input="onInput"
      @blur="$emit('blur', $event)"
      @focus="$emit('focus', $event)"
      @keyup.enter="$emit('enter')"
    />
    <p v-if="hint" class="field-hint">{{ hint }}</p>
    <p v-if="error" class="field-error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: string | number | null
  label?: string
  type?: string
  placeholder?: string
  disabled?: boolean
  required?: boolean
  hint?: string
  error?: string
  min?: number | string
  max?: number | string
  step?: number | string
  id?: string
}>(), {
  type: 'text',
  disabled: false,
  required: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number | null]
  blur: [event: FocusEvent]
  focus: [event: FocusEvent]
  enter: []
}>()

const generatedId = useId()
const inputId = computed(() => props.id || `input-${generatedId}`)

const onInput = (event: Event) => {
  const target = event.target as HTMLInputElement
  const value = props.type === 'number'
    ? (target.value === '' ? null : Number(target.value))
    : target.value
  emit('update:modelValue', value)
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
  transition: border-color 0.2s, box-shadow 0.2s;
}

.custom-input:focus {
  border-color: #22c1c3;
  box-shadow: 0 0 0 4px rgba(34, 193, 195, 0.25);
}

.custom-input:disabled {
  background: rgba(255, 255, 255, 0.5);
  cursor: not-allowed;
}

.custom-input::placeholder {
  color: #999;
}

.field-hint {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  margin: 0;
}

.field-error {
  color: #ff6b6b;
  font-size: 12px;
  margin: 0;
}
</style>