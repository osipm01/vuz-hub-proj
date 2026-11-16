<template>
  <div class="dashboard-page">
    <h1 class="page-title">Главная</h1>

    <div v-if="user" class="user-info">
      <p class="welcome-text">Добро пожаловать, {{ user.name }}</p>
      <p class="user-details">
        Email: {{ user.email }} | Роль: {{ user.role }}
      </p>
    </div>

    <div v-if="error" class="error-box">
      <p>{{ error }}</p>
      <BaseButton variant="danger" @click="handleRetry">Повторить</BaseButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { UserRead } from '~/types/user'
import { useToast } from '~/composables/useToast'

definePageMeta({
  middleware: 'auth',
})

const toast: ReturnType<typeof useToast> = useToast()
const user: Ref<UserRead | null> = ref(null)
const error: Ref<string | null> = ref(null)

const fetchUserData = async (): Promise<void> => {
  try {
    error.value = null
    user.value = await $fetch<UserRead>('/api/auth/me')
  }
  catch (err: unknown) {
    if (err instanceof Error && 'statusCode' in err) {
      const status: number = (err as { statusCode: number }).statusCode

      if (status === 401) {
        return navigateTo('/auth')
      }
    }

    error.value = 'Не удалось загрузить данные'
    toast.addError('Не удалось загрузить данные')
  }
}

const handleRetry = (): void => {
  fetchUserData()
}

await fetchUserData()
</script>

<style scoped>
.dashboard-page {
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-title {
  color: #ffffff;
  font-size: 28px;
  margin: 0;
}

.user-info {
  padding: 24px;
  background: rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
}

.welcome-text {
  color: #ffffff;
  font-size: 20px;
  margin: 0 0 12px 0;
}

.user-details {
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  margin: 0;
}

.error-box {
  padding: 24px;
  background: rgba(231, 29, 54, 0.15);
  border: 1px solid rgba(231, 29, 54, 0.3);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.error-box p {
  color: #ff6b6b;
  margin: 0;
}
</style>
