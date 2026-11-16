export default defineNuxtRouteMiddleware((to) => {
  const protectedPaths: Array<string> = ['/', '/users', '/media']
  const isAuthenticated: boolean = useState<boolean>('auth:isAuthenticated', () => false)

  const isProtected: boolean = protectedPaths.some(
    (path: string) => to.path === path || to.path.startsWith(`${path}/`)
  )

  const isLoginPage: boolean = to.path === '/auth'

  if (isProtected && isAuthenticated.value !== true) {
    return '/auth'
  }

  if (isLoginPage && isAuthenticated.value === true) {
    return '/'
  }
})
