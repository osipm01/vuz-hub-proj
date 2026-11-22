export default defineEventHandler(async (event) => {
  const body: { email: string; password: string } = await readBody(event)

  const response: Response = await fetch('http://localhost:80/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  const data: Record<string, unknown> = await response.json()

  if (response.ok && data.access_token) {
    setCookie(event, 'access_token', data.access_token as string, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 1800,
      path: '/',
    })
  }

  setResponseStatus(event, response.status)
  return data
})
