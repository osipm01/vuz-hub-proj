<template>
  <button
    :type="nativeType"
    :disabled="disabled || loading"
    class="btn-action"
    :class="[`btn-${variant}`, sizeClass, { 'btn-loading': loading }]"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="btn-spinner"></span>
    <slot>{{ loading ? loadingText : label }}</slot>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  label?: string
  loadingText?: string
  variant?: 'success' | 'danger' | 'primary' | 'secondary' | 'warning' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  nativeType?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  loading?: boolean
}>(), {
  variant: 'primary',
  size: 'md',
  nativeType: 'button',
  disabled: false,
  loading: false,
})

defineEmits<{
  click: [event: MouseEvent]
}>()

const sizeClass = computed(() => props.size === 'sm' ? 'btn-small' : '')
</script>

<style scoped>
.btn-action {
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: opacity 0.2s, transform 0.1s, background 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-decoration: none;
}

.btn-action:active {
  transform: scale(0.98);
}

.btn-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-small {
  padding: 6px 12px;
  font-size: 13px;
}

.btn-success {
  background-color: #2ec4b6;
  color: white;
  width: max-content;
}

.btn-success:hover:not(:disabled) {
  background-color: #25a99c;
}

.btn-danger {
  background-color: #e71d36;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background-color: #c9182d;
}

.btn-primary {
  background-color: #0077aa;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #00609a;
}

.btn-secondary {
  background-color: rgba(255, 255, 255, 0.15);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.btn-secondary:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.25);
}

.btn-warning {
  background-color: #ff9f1c;
  color: white;
  padding: 6px 12px;
  font-size: 13px;
}

.btn-warning:hover:not(:disabled) {
  background-color: #e88a0e;
}

.btn-loading {
  position: relative;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>