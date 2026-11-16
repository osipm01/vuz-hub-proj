<template>
  <div class="input-field-group">
    <label v-if="label" :for="textareaId" class="field-label">{{ label }}</label>
    <textarea
      :id="textareaId"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :required="required"
      :rows="rows"
      class="custom-input custom-textarea"
      @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    ></textarea>
    <p v-if="hint" class="field-hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: string
  label?: string
  placeholder?: string
  disabled?: boolean
  required?: boolean
  hint?: string
  rows?: number
  id?: string
}>(), {
  rows: 4,
  disabled: false,
  required: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const generatedId = useId()
const textareaId = computed(() => props.id || `textarea-${generatedId}`)
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

.custom-input:disabled {
  background: rgba(255, 255, 255, 0.5);
  cursor: not-allowed;
}

.custom-textarea {
  min-height: 100px;
  resize: vertical;
  font-family: inherit;
}

.field-hint {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  margin: 0;
}
</style>