import { useAuthHydration } from '~/composables/useAuthHydration'

export default defineNuxtRouteMiddleware(async () => {
  // Hydrate auth state from server cookie before routing
  const { useNuxtApp } = await import('#app')
  const nuxtApp: NuxtApp = useNuxtApp()

  if (import.meta.server && nuxtApp.ssrContext) {
    const event: H3Event = nuxtApp.ssrContext.event as H3Event
    const token: string | undefined = getCookie(event, 'access_token')

    if (token) {
      try {
        const res: Response = await fetch('http://localhost:8001/users/me', {
          method: 'GET',
          headers: { 'Authorization': `Bearer ${token}` },
        })

        if (res.ok) {
          const user: UserRead = await res.json()
          useState<AuthState>('auth:state').value = {
            authenticated: true,
            user,
            pending: false,
          }
        }
      }
      catch {
        /* invalid token */
      }
    }
  }
})
