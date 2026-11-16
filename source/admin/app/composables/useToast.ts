import { v4 as uuidv4 } from 'uuid'
import { ToastType, type ToastMessage } from '~/types/toast'

export class ToastManager {
  private static instance: ToastManager | null = null

  static getInstance(): ToastManager {
    if (ToastManager.instance === null) {
      ToastManager.instance = new ToastManager()
    }
    return ToastManager.instance
  }

  static resetInstance(): void {
    ToastManager.instance = null
  }

  addSuccess(message: string, duration: number = 4000): void {
    this.add(message, ToastType.Success, duration)
  }

  addError(message: string, duration: number = 5000): void {
    this.add(message, ToastType.Error, duration)
  }

  addWarning(message: string, duration: number = 4000): void {
    this.add(message, ToastType.Warning, duration)
  }

  addInfo(message: string, duration: number = 4000): void {
    this.add(message, ToastType.Info, duration)
  }

  removeToast(id: string): void {
    const toasts: Array<ToastMessage> = useState<Array<ToastMessage>>('toast:list', () => [])
    const filtered: Array<ToastMessage> = toasts.filter((item: ToastMessage) => item.id !== id)
    toasts.value = filtered
  }

  private add(message: string, type: ToastType, duration: number): void {
    const toasts: Array<ToastMessage> = useState<Array<ToastMessage>>('toast:list', () => [])
    const toastItem: ToastMessage = {
      id: uuidv4(),
      text: message,
      type,
      duration,
    }

    toasts.value = [...toasts.value, toastItem]

    if (duration > 0) {
      setTimeout(() => this.removeToast(toastItem.id), duration)
    }
  }
}

export function useToast(): ToastManager {
  return ToastManager.getInstance()
}
