import { ApiError } from '~/types/apiError'

const API_BASE_URL: string = 'http://localhost:80'

export class ApiService {
  private readonly baseUrl: string
  private cookieSupported: boolean | null = null

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private detectCookieSupport(): boolean {
    if (this.cookieSupported !== null) {
      return this.cookieSupported
    }

    this.cookieSupported = navigator.cookieEnabled === true
    return this.cookieSupported
  }

  private buildHeaders(customHeaders: Record<string, string> | null): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...customHeaders,
    }

    if (this.detectCookieSupport()) {
      headers['X-Auth-Cookies'] = 'true'
    }

    return headers
  }

  private buildConfig(customHeaders: Record<string, string> | null, method: string): RequestInit {
    return {
      method,
      headers: this.buildHeaders(customHeaders),
      credentials: 'include',
    }
  }

  private async request<T>(
    endpoint: string,
    method: string,
    body: unknown | null = null,
    customHeaders: Record<string, string> | null = null
  ): Promise<T> {
    const config: RequestInit = this.buildConfig(customHeaders, method)

    if (body !== null) {
      config.body = JSON.stringify(body)
    }

    const response: Response = await fetch(`${this.baseUrl}${endpoint}`, config)

    if (!response.ok) {
      const errorDetail: string | null = await this.readErrorDetail(response)

      if (response.status === 401 || response.status === 403) {
        throw new AuthError(errorDetail || 'Не авторизован', response.status)
      }

      if (response.status === 422) {
        throw new ValidationError(errorDetail || 'Ошибка валидации', null)
      }

      throw new ApiError(errorDetail || 'Ошибка запроса', response.status)
    }

    if (response.status === 204) {
      return null as T
    }

    return response.json() as Promise<T>
  }

  private async readErrorDetail(response: Response): Promise<string | null> {
    try {
      const errorBody: Record<string, unknown> = await response.json()
      return (errorBody.message as string) || null
    }
    catch {
      return null
    }
  }

  get<T>(endpoint: string, headers: Record<string, string> | null = null): Promise<T> {
    return this.request<T>(endpoint, 'GET', null, headers)
  }

  post<T>(endpoint: string, body: unknown, headers: Record<string, string> | null = null): Promise<T> {
    return this.request<T>(endpoint, 'POST', body, headers)
  }

  put<T>(endpoint: string, body: unknown, headers: Record<string, string> | null = null): Promise<T> {
    return this.request<T>(endpoint, 'PUT', body, headers)
  }

  patch<T>(endpoint: string, body: unknown, headers: Record<string, string> | null = null): Promise<T> {
    return this.request<T>(endpoint, 'PATCH', body, headers)
  }

  delete<T>(endpoint: string, headers: Record<string, string> | null = null): Promise<T> {
    return this.request<T>(endpoint, 'DELETE', null, headers)
  }
}
