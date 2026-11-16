import type { UserRead } from '~/types/user'

export default defineNitroPlugin(async (nitroApp) => {
  nitroApp.hooks.hook('render:response', async (response, { event }) => {
    const token: string | undefined = getCookie(event, 'access_token')

    if (token) {
      try {
        const res: Response = await fetch('http://localhost:8001/users/me', {
          method: 'GET',
          headers: { 'Authorization': `Bearer ${token}` },
        })

        if (res.ok) {
          const user: UserRead = await res.json()
          const nuxtApp: NuxtApp = useNuxtApp()
          nuxtApp.payload.state['auth:state'] = {
            authenticated: true,
            user,
            pending: false,
          }
        }
      }
      catch {
        /* token invalid */
      }
    }
  })
})
