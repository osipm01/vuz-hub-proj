<template>
  <div class="auth-page">
    <Transition name="water-float" appear>
      <div class="auth-shell">
        <h1 class="auth-title">Вход в систему</h1>

        <form @submit.prevent="handleLogin">
          <BaseFormField :error="emailError" label="Email">
            <BaseInput
              v-model="email"
              type="email"
              placeholder="user@example.com"
              :disabled="isSubmitting"
            />
          </BaseFormField>

          <BaseFormField :error="passwordError" label="Пароль">
            <BaseInput
              v-model="password"
              type="password"
              placeholder="Введите пароль"
              :disabled="isSubmitting"
            />
          </BaseFormField>

          <p v-if="genericError" class="error-message">{{ genericError }}</p>

          <BaseButton
            native-type="submit"
            variant="primary"
            :loading="isSubmitting"
            label="Войти"
          >
            Войти
          </BaseButton>
        </form>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import type { LoginRequest } from '~/types/auth'
import { AuthError, ValidationError, ApiError } from '~/types/apiError'
import { useToast } from '~/composables/useToast'

interface FormErrors {
  emailError: string | null
  passwordError: string | null
  genericError: string | null
}

definePageMeta({
  middleware: 'auth',
  layout: false,
})

const router: ReturnType<typeof useRouter> = useRouter()
const toast: ReturnType<typeof useToast> = useToast()
const email: Ref<string> = ref('')
const password: Ref<string> = ref('')
const isSubmitting: Ref<boolean> = ref(false)
const errors: FormErrors = reactive({
  emailError: null,
  passwordError: null,
  genericError: null,
})

const clearErrors = (): void => {
  errors.emailError = null
  errors.passwordError = null
  errors.genericError = null
}

const validateInput = (): boolean => {
  clearErrors()

  if (!email.value) {
    errors.emailError = 'Email обязателен'
    return false
  }

  if (!password.value) {
    errors.passwordError = 'Пароль обязателен'
    return false
  }

  return true
}

const handleLogin = async (): Promise<void> => {
  if (validateInput() === false) {
    return
  }

  isSubmitting.value = true

  try {
    const loginRequest: LoginRequest = { email: email.value, password: password.value }
    await $fetch('/api/auth/login', { method: 'POST', body: loginRequest })

    useState<boolean>('auth:isAuthenticated', () => true).value = true
    toast.addSuccess('Вы успешно вошли в систему')
    router.push('/')
  }
  catch (err: unknown) {
    clearErrors()

    if (err instanceof ValidationError) {
      if (err.field === 'email') {
        errors.emailError = err.message
      }
      else {
        errors.passwordError = err.message
      }
    }
    else if (err instanceof AuthError) {
      errors.genericError = 'Неверный email или пароль'
      toast.addError('Неверный email или пароль')
    }
    else if (err instanceof ApiError) {
      errors.genericError = err.message
      toast.addError(err.message)
    }
    else {
      errors.genericError = 'Произошла ошибка. Попробуйте позже'
      toast.addError('Произошла ошибка. Попробуйте позже')
    }
  }
  finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.auth-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  width: 100%;
}

.auth-shell {
  width: 100%;
  max-width: 420px;
  padding: 32px;
  margin: 16px;
  background: rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.auth-title {
  color: #ffffff;
  text-align: center;
  font-size: 24px;
  margin: 0 0 8px 0;
}

.error-message {
  color: #ff6b6b;
  font-size: 14px;
  margin: 0;
  text-align: center;
}
</style>
