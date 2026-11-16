<template>
  <Transition name="water-float" appear>
    <div class="form-shell" >
      <div class="form-content">
        <slot></slot>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
defineProps<{
  show?: boolean
}>()
</script>

<style scoped>
/* --- Анимация появления / исчезновения --- */
.water-float-enter-from {
  opacity: 0;
  transform: translateY(60px) scale(0.92);
  filter: blur(15px);
}

.water-float-enter-active {
  transition:
    opacity 0.8s ease-out,
    transform 0.9s cubic-bezier(0.16, 1, 0.3, 1),
    filter 0.7s ease-out;
}

.water-float-enter-to {
  opacity: 1;
  transform: translateY(0) scale(1);
  filter: blur(0);
}

.water-float-leave-active {
  transition: all 0.5s ease-in;
}

.water-float-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.96);
  filter: blur(8px);
}

/* --- Оболочка формы (glassmorphism) --- */
.form-shell {
  width: 100%;
  max-width: 650px;
  max-height: calc(100vh - 120px);
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.12);
  color: #ffffff;
  box-sizing: border-box;
  overflow-y: auto;
  overflow-x: hidden;
  will-change: transform, opacity, filter;
}

/* --- Кастомный скроллбар --- */
.form-shell::-webkit-scrollbar {
  width: 8px;
}

.form-shell::-webkit-scrollbar-track {
  background: transparent;
}

.form-shell::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

.form-shell::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.35);
}

/* Firefox */
.form-shell {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
}

/* --- Контент формы --- */
.form-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* --- Наследуемые стили для вложенных элементов --- */
:deep(.form-group) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:deep(.form-label) {
  font-size: 0.9rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
}

:deep(.form-input) {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 12px 16px;
  color: #ffffff;
  font-size: 0.95rem;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
}

:deep(.form-input::placeholder) {
  color: rgba(255, 255, 255, 0.35);
}

:deep(.form-input:focus) {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.5);
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.1);
}
</style>