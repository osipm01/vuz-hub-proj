export default defineEventHandler(async (event) => {
  const token: string | undefined = getCookie(event, 'access_token')

  if (!token) {
    throw createError({ statusCode: 401, statusMessage: 'Unauthorized' })
  }

  const response: Response = await fetch('http://localhost:8001/users/me', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    throw createError({ statusCode: 401, statusMessage: 'Session expired' })
  }

  return response.json()
})
