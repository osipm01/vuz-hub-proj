<template>
  <div class="users-page">
    <h1 class="page-title">Пользователи</h1>

    <div v-if="isLoading" class="loading-state">Загрузка...</div>

    <div v-if="error" class="error-box">
      <p>{{ error }}</p>
      <BaseButton variant="danger" @click="loadUsers">Повторить</BaseButton>
    </div>

    <div v-if="users.length > 0" class="users-table-wrapper">
      <table class="users-table">
        <thead>
          <tr>
            <th class="col-id">ID</th>
            <th class="col-name">Имя</th>
            <th class="col-email">Email</th>
            <th class="col-role">Роль</th>
            <th class="col-created">Дата регистрации</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="userItem in users" :key="userItem.id">
            <td class="col-id">{{ userItem.id }}</td>
            <td class="col-name">{{ userItem.name }}</td>
            <td class="col-email">{{ userItem.email }}</td>
            <td class="col-role">{{ userItem.role }}</td>
            <td class="col-created">{{ formatUserDate(userItem.createdAt) }}</td>
          </tr>
        </tbody>
      </table>
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
const users: Ref<Array<UserRead>> = ref([])
const isLoading: Ref<boolean> = ref(false)
const error: Ref<string | null> = ref(null)

const formatUserDate = (dateString: string): string => {
  const date: Date = new Date(dateString)
  return date.toLocaleDateString('ru-RU')
}

const loadUsers = async (): Promise<void> => {
  isLoading.value = true
  error.value = null

  try {
    users.value = await $fetch<UserRead[]>('/api/auth/users')
  }
  catch (err: unknown) {
    if (err instanceof Error && 'statusCode' in err) {
      const status: number = (err as { statusCode: number }).statusCode

      if (status === 401) {
        return navigateTo('/auth')
      }
    }

    error.value = 'Не удалось загрузить список пользователей'
    toast.addError('Не удалось загрузить список пользователей')
  }
  finally {
    isLoading.value = false
  }
}

await loadUsers()
</script>

<style scoped>
.users-page {
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

.loading-state {
  color: rgba(255, 255, 255, 0.7);
  font-size: 16px;
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

.users-table-wrapper {
  overflow-x: auto;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
  color: #ffffff;
}

.users-table th,
.users-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.users-table th {
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
  font-weight: 500;
  text-transform: uppercase;
}

.users-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.05);
}

.col-id { width: 60px; }
.col-name { flex: 1; }
.col-email { flex: 2; }
.col-role { width: 140px; }
.col-created { width: 140px; }
</style>
