export default defineEventHandler(async (event) => {
  const protectedPaths: Array<string> = ['/', '/users', '/media']
  const pathname: string = new URL(getRequestURL(event).pathname)

  const isProtected: boolean = protectedPaths.some(
    (path: string) => pathname.pathname === path || pathname.pathname.startsWith(`${path}/`)
  )

  if (isProtected) {
    const token: string | undefined = getCookie(event, 'access_token')

    if (!token) {
      event.context.redirected = '/auth'
    }
    else {
      try {
        const response: Response = await fetch('http://localhost:8001/users/me', {
          method: 'GET',
          headers: { 'Authorization': `Bearer ${token}` },
        })

        if (!response.ok) {
          deleteCookie(event, 'access_token', { path: '/' })
          event.context.redirected = '/auth'
        }
      }
      catch {
        event.context.redirected = '/auth'
      }
    }
  }
})
