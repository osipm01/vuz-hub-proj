import type { TokenResponse, LoginRequest, RegisterRequest, AuthState, UserRead } from '~/types/auth'
import type { UserRole } from '~/types/user'
import { ApiService } from './ApiService'
import { AuthError } from '~/types/apiError'

export class AuthService {
  private readonly api: ApiService
  private state: AuthState = {
    isAuthenticated: false,
    user: null,
    token: null,
  }

  constructor(api: ApiService = new ApiService()) {
    this.api = api
  }

  getState(): AuthState {
    return { ...this.state }
  }

  isLoggedIn(): boolean {
    return this.state.isAuthenticated === true
  }

  getUser(): UserRead | null {
    return this.state.user
  }

  getToken(): string | null {
    return this.state.token
  }

  getRole(): UserRole | null {
    if (this.state.user === null) {
      return null
    }
    return this.state.user.role
  }

  hasRole(targetRole: UserRole): boolean {
    return this.getRole() === targetRole
  }

  async login(request: LoginRequest): Promise<TokenResponse> {
    const response: TokenResponse = await this.api.post<TokenResponse>(
      '/auth/login',
      request
    )

    this.state.token = response.accessToken
    this.state.isAuthenticated = true

    const user: UserRead = await this.api.get<UserRead>('/users/me')
    this.state.user = user

    return response
  }

  async register(request: RegisterRequest): Promise<TokenResponse> {
    const response: TokenResponse = await this.api.post<TokenResponse>(
      '/auth/register',
      request
    )

    this.state.token = response.accessToken
    this.state.isAuthenticated = true

    const user: UserRead = await this.api.get<UserRead>('/users/me')
    this.state.user = user

    return response
  }

  async fetchMe(): Promise<UserRead> {
    const user: UserRead = await this.api.get<UserRead>('/users/me')
    this.state.user = user
    this.state.isAuthenticated = true
    return user
  }

  async logout(): Promise<void> {
    try {
      await this.api.post<void>('/auth/logout', null)
    }
    finally {
      this.reset()
    }
  }

  reset(): void {
    this.state = {
      isAuthenticated: false,
      user: null,
      token: null,
    }
  }
}
