<template>
  <Transition name="slide-fade" appear>
    <div class="glass-panel">
      <!-- Заголовок панели -->
      <header v-if="title || $slots.header" class="panel-header">
        <slot name="header">
          <h3>{{ title }}</h3>
        </slot>
      </header>
      <NavPath />
      <!-- Основное содержимое панели -->
      <div class="panel-content">
        <slot></slot>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import NavPath from './base/NavPath.vue';

defineProps<{
  title?: string
}>()
</script>

<style scoped>
.glass-panel {
  /* Занимает всю доступную ширину и высоту родительского контейнера */
  width: 100%;
  height: 100%;
  min-height: calc(100vh - 40px); /* Гарантирует растягивание на весь экран минус отступы */
  
  /* Эффект матового стекла (Glassmorphism) */
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  
  /* Границы и скругления */
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 16px;
  
  /* Внутренние отступы и расчет размеров */
  padding: 24px;
  box-sizing: border-box;
  
  /* Отображение контента гибким flex-боксом */
  display: flex;
  flex-direction: column;
  gap: 20px;
  
  /* Базовые стили текста */
  color: #ffffff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.panel-header h3 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  opacity: 0.9;
}

.panel-content {
  flex: 1; /* Заставляет контент занимать все оставшееся место */
  width: 100%;
}

/* Анимация плавного появления (slide-fade) */
.slide-fade-enter-active {
  transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-fade-leave-active {
  transition: all 0.4s cubic-bezier(0.7, 0, 0.84, 0);
}

.slide-fade-enter-from {
  transform: translateY(20px) scale(0.98);
  opacity: 0;
}

.slide-fade-leave-to {
  transform: translateY(-20px);
  opacity: 0;
}
</style>
