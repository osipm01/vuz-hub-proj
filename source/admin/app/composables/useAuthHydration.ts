import type { UserRead } from '~/types/user'

interface AuthState {
  authenticated: boolean
  user: UserRead | null
}

const state: Ref<AuthState> = useState<AuthState>('auth:state', () => ({
  authenticated: false,
  user: null,
}))

export function useAuthHydration(): Ref<boolean> {
  const isAuthenticated: Ref<boolean> = computed(() => state.value.authenticated)

  if (import.meta.client && !state.value.authenticated) {
    const checkAuth = async (): Promise<void> => {
      try {
        const user: UserRead = await $fetch<UserRead>('/api/auth/me')
        state.value = { authenticated: true, user }
      }
      catch {
        state.value = { authenticated: false, user: null }
      }
    }
    checkAuth()
  }

  return isAuthenticated
}
