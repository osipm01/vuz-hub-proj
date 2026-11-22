import type { UserRead } from '~/types/user'

interface AuthState {
  authenticated: boolean
  user: UserRead | null
  pending: boolean
}

export function useAuthHydration(): Ref<AuthState> {
  // Вызываем useState строго внутри композабла
  const state = useState<AuthState>('auth:state', () => ({
    authenticated: false,
    user: null,
    pending: true,
  }))

  // Запускаем проверку только на клиенте и только один раз, пока pending === true
  if (import.meta.client && state.value.pending) {
    $fetch<UserRead>('/api/auth/me')
      .then((user) => {
        state.value = {
          authenticated: true,
          user,
          pending: false,
        }
      })
      .catch(() => {
        state.value = {
          authenticated: false,
          user: null,
          pending: false,
        }
      })
  }

  return state
}
