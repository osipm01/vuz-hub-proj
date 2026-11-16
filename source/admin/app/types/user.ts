export enum UserRole {
  User = 'user',
  Admin = 'admin',
  Dispatcher = 'dispatcher',
}

export interface UserRead {
  id: number
  name: string
  email: string
  groupId: number | null
  role: UserRole
  createdAt: string
}
