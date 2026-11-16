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

  // Hydrate from server cookie during SSR before client navigation
  if (import.meta.server) {
    const token: string | undefined = getCookie(useNuxtApp().ssrContext.event, 'access_token')

    if (token) {
      try {
        const res: Response = await fetch('http://localhost:8001/users/me', {
          method: 'GET',
          headers: { 'Authorization': `Bearer ${token}` },
        })

        if (res.ok) {
          const user: UserRead = await res.json()
          state.value = { authenticated: true, user, pending: false }
        }
      }
      catch {
        /* invalid token */
      }
    }
  }

  // If pending on client (fresh reload), skip — server already handled auth
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
