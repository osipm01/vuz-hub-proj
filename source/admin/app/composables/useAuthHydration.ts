import type { UserRead } from '~/types/user'

interface AuthState {
  authenticated: boolean
  user: UserRead | null
  pending: boolean
}

const state: AuthState = useState<AuthState>('auth:state', () => ({
  authenticated: false,
  user: null,
  pending: true,
}))

export function useAuthHydration(): void {
  if (import.meta.server) {
    return
  }

  const check: () => Promise<void> = async () => {
    try {
      const user: UserRead = await $fetch<UserRead>('/api/auth/me')
      state.value = {
        authenticated: true,
        user,
        pending: false,
      }
    }
    catch {
      state.value = {
        authenticated: false,
        user: null,
        pending: false,
      }
    }
  }

  // Run immediately on hydration, not onMounted
  check()
}

export function getAuthState(): AuthState {
  return state.value
}
