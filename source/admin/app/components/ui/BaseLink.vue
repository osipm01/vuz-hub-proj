<template>
  <NuxtLink
    :to="to"
    class="btn-action"
    :class="[`btn-${variant}`, sizeClass]"
  >
    <slot>{{ label }}</slot>
  </NuxtLink>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  to: string
  label?: string
  variant?: 'success' | 'danger' | 'primary' | 'secondary' | 'warning' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
}>(), {
  variant: 'secondary',
  size: 'md',
})

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

.btn-small {
  padding: 6px 12px;
  font-size: 13px;
}

.btn-success {
  background-color: #2ec4b6;
  color: white;
  width: max-content;
}

.btn-success:hover {
  background-color: #25a99c;
}

.btn-danger {
  background-color: #e71d36;
  color: white;
}

.btn-danger:hover {
  background-color: #c9182d;
}

.btn-primary {
  background-color: #0077aa;
  color: white;
}

.btn-primary:hover {
  background-color: #00609a;
}

.btn-secondary {
  background-color: rgba(255, 255, 255, 0.15);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.btn-secondary:hover {
  background-color: rgba(255, 255, 255, 0.25);
}

.btn-warning {
  background-color: #ff9f1c;
  color: white;
}

.btn-warning:hover {
  background-color: #e88a0e;
}
</style>