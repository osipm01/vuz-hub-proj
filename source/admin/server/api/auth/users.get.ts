export default defineEventHandler(async (event) => {
  const token: string | undefined = getCookie(event, 'access_token')

  if (!token) {
    throw createError({ statusCode: 401, statusMessage: 'Unauthorized' })
  }

  const query: Record<string, string> = getQuery(event)
  const params: URLSearchParams = new URLSearchParams()

  if (query.skip) params.set('skip', query.skip)
  if (query.limit) params.set('limit', query.limit)
  if (query.group_id) params.set('group_id', query.group_id)

  const url: string = `/users/?${params.toString()}`

  const response: Response = await fetch(`http://localhost:8001${url}`, {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` },
  })

  if (!response.ok) {
    throw createError({ statusCode: response.status, statusMessage: 'Ошибка загрузки' })
  }

  return response.json()
})
