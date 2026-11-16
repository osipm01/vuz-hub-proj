export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public detail: string | null = null
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export class AuthError extends ApiError {
  constructor(message: string, statusCode: number = 401) {
    super(message, statusCode)
    this.name = 'AuthError'
  }
}

export class ValidationError extends ApiError {
  constructor(message: string, public field: string | null = null) {
    super(message, 422, field)
    this.name = 'ValidationError'
  }
}
