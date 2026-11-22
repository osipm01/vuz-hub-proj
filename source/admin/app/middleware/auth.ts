import type { UserRead } from '~/types/user'

interface AuthState {
  authenticated: boolean
  user: UserRead | null
}

export default defineNuxtRouteMiddleware((to) => {
  const state: AuthState = useState<AuthState>('auth:state', () => ({
    authenticated: false,
    user: null,
  }))

  const protectedPaths: Array<string> = ['/', '/users', '/media']
  const isProtected: boolean = protectedPaths.some(
    (path: string) => to.path === path || to.path.startsWith(`${path}/`)
  )

  const isLoginPage: boolean = to.path === '/auth'

  if (isProtected && !state.value.authenticated) {
    return navigateTo('/auth')
  }

  if (isLoginPage && state.value.authenticated) {
    return navigateTo('/')
  }
})
