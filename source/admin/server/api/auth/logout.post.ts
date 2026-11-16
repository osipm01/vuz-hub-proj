export default defineEventHandler(async (event) => {
  deleteCookie(event, 'access_token', { path: '/' })

  return sendNoContent(event, 204)
})
