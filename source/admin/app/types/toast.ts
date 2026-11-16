export enum ToastType {
  Success = 'success',
  Error = 'error',
  Warning = 'warning',
  Info = 'info',
}

export interface ToastMessage {
  id: string
  text: string
  type: ToastType
  duration: number
}
