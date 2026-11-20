// import { useState } from 'vue'
import type { UserRead } from '~/types/user'
import { getCookie } from 'h3'

interface AuthState {
  authenticated: boolean
  user: UserRead | null
  pending: boolean
}

export default defineNuxtRouteMiddleware(async (to) => {
  const state = useState<AuthState>('auth:state', () => ({
    authenticated: false,
    user: null,
    pending: true,
  }))

  // Читаем куку нативным способом Nuxt (работает и на SSR, и на клиенте)
  const token = useCookie<string | null>('access_token')

  // Проверяем токен на сервере при первом заходе (или если статус ещё pending)
  if (import.meta.server && state.value.pending) {
    if (token.value) {
      try {
        const user = await $fetch<UserRead>('http://localhost:8001/users/me', {
          headers: { Authorization: `Bearer ${token.value}` },
        })
        state.value = { authenticated: true, user, pending: false }
      }
      catch {
        // Токен невалидный или протух
        token.value = null
        state.value = { authenticated: false, user: null, pending: false }
      }
    }
    else {
      // Токена нет — сразу снимаем статус pending, чтобы сработал редирект на /auth
      state.value.pending = false
    }
  }

  const protectedPaths = ['/', '/users', '/media']
  const isProtected = protectedPaths.some(
    path => to.path === path || to.path.startsWith(`${path}/`),
  )

  const isLoginPage = to.path === '/auth'

  if (isProtected && !state.value.authenticated) {
    return navigateTo('/auth')
  }

  if (isLoginPage && state.value.authenticated) {
    return navigateTo('/')
  }
})
