import { useState } from 'vue'
import type { UserRead } from '~/types/user'

interface AuthState {
  authenticated: boolean
  user: UserRead | null
  pending: boolean
}

export default defineNuxtRouteMiddleware(async (to) => {
  const state: AuthState = useState<AuthState>('auth:state', () => ({
    authenticated: false,
    user: null,
    pending: true,
  }))

  // If still pending (fresh page load), skip client-side check.
  // Server middleware already handled auth.
  if (state.value.pending) {
    return
  }

  const protectedPaths: Array<string> = ['/', '/users', '/media']
  const isProtected: boolean = protectedPaths.some(
    (path: string) => to.path === path || to.path.startsWith(`${path}/`)
  )

  const isLoginPage: boolean = to.path === '/auth'

  if (isProtected && !state.value.authenticated) {
    return '/auth'
  }

  if (isLoginPage && state.value.authenticated) {
    return '/'
  }
})
