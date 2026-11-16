<template>
  <Teleport to="body">
    <TransitionGroup name="toast-list" tag="div" class="toast-container">
      <div
        v-for="item in toasts"
        :key="item.id"
        class="toast-item"
        :class="`toast-${item.type}`"
      >
        <span class="toast-icon">{{ iconMap[item.type] }}</span>
        <span class="toast-text">{{ item.text }}</span>
        <button class="toast-close" @click="removeToast(item.id)">×</button>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToastMessage } from '~/types/toast'

const toastState: Array<ToastMessage> = useState<Array<ToastMessage>>('toast:list', () => [])
const toasts: Readonly<Array<ToastMessage>> = computed(() => toastState.value)

const removeToast: (id: string) => void = (id: string) => {
  const updated: Array<ToastMessage> = toasts.value.filter((item: ToastMessage) => item.id !== id)
  toastState.value = updated
}

const iconMap: Record<string, string> = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 999999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
  max-width: 360px;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #1a1a2e;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  pointer-events: auto;
  color: #ffffff;
  font-size: 14px;
  border-left: 4px solid;
}

.toast-success {
  border-left-color: #2ec4b6;
}

.toast-error {
  border-left-color: #e71d36;
}

.toast-warning {
  border-left-color: #ff9f1c;
}

.toast-info {
  border-left-color: #0077aa;
}

.toast-icon {
  font-size: 16px;
  font-weight: 600;
  flex-shrink: 0;
}

.toast-text {
  flex: 1;
  word-break: break-word;
}

.toast-close {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.5);
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
  flex-shrink: 0;
  transition: color 0.2s;
}

.toast-close:hover {
  color: #ffffff;
}

.toast-list-enter-active {
  transition: all 0.3s ease;
}

.toast-list-leave-active {
  transition: all 0.2s ease;
}

.toast-list-enter-from {
  opacity: 0;
  transform: translateX(50px);
}

.toast-list-leave-to {
  opacity: 0;
  transform: translateX(50px);
}
</style>
