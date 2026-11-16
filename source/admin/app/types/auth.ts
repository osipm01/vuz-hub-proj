import type { UserRead } from './user'

export interface TokenResponse {
  accessToken: string
  refreshToken: string
  tokenType: string
  userId: number
  role: string
  isNewUser: boolean
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  fullName?: string
}

export interface AuthState {
  isAuthenticated: boolean
  user: UserRead | null
  token: string | null
}
