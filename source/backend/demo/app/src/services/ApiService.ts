// src/services/ApiService.ts

/** ---------- Типы, соответствующие backend ---------- */

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface JobMetrics {
  [key: string]: number | string | null;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  metrics?: JobMetrics | null;
  download_url?: string | null;
}

export interface DemoJobParams {
  n_teachers: number;
  n_groups: number;
  n_rooms: number;
  pop_size: number;
  generations: number;
  elite: number;
  workers: number;
}

export interface UploadJobParams {
  /** Параметры передаются как form-data поля */
  pop_size?: number;
  generations?: number;
  elite?: number;
  workers?: number;
}

export interface ApiServiceOptions {
  /** Базовый URL API, по умолчанию http://127.0.0.1:8000 */
  baseUrl?: string;
  /** Заголовки, добавляемые к каждому запросу (например, Authorization) */
  defaultHeaders?: Record<string, string>;
  /** Таймаут запроса в мс (0 = без таймаута), по умолчанию 30_000 */
  timeoutMs?: number;
  /** Колбэк для логирования ошибок */
  onError?: (err: unknown, context: string) => void;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/** ---------- Синглтон ---------- */

export class ApiService {
  private static _instance: ApiService | null = null;

  private readonly baseUrl: string;
  private readonly defaultHeaders: Record<string, string>;
  private readonly timeoutMs: number;
  private readonly onError?: (err: unknown, context: string) => void;

  private constructor(options: ApiServiceOptions = {}) {
    this.baseUrl = (options.baseUrl ?? 'http://127.0.0.1:8000').replace(/\/+$/, '');
    this.defaultHeaders = { ...(options.defaultHeaders ?? {}) };
    this.timeoutMs = options.timeoutMs ?? 30_000;
    this.onError = options.onError;
  }

  /** Получить единственный экземпляр сервиса. */
  static getInstance(options?: ApiServiceOptions): ApiService {
    if (!ApiService._instance) {
      ApiService._instance = new ApiService(options);
    }
    return ApiService._instance;
  }

  /** Явный сброс (полезно в тестах). */
  static resetInstance(): void {
    ApiService._instance = null;
  }

  /** Позволяет задать/обновить базовые заголовки (например, токен). */
  setDefaultHeaders(headers: Record<string, string>): void {
    Object.assign(this.defaultHeaders, headers);
  }

  /** ---------- Низкоуровневый запрос ---------- */

  private async request<T>(
    path: string,
    init: RequestInit = {},
    context = 'request',
  ): Promise<T> {
    const controller = new AbortController();
    const timer =
      this.timeoutMs > 0
        ? setTimeout(() => controller.abort(), this.timeoutMs)
        : null;

    // Объединяем внешний signal (если передан) с внутренним
    const externalSignal = init.signal;
    if (externalSignal) {
      externalSignal.addEventListener('abort', () => controller.abort(), {
        once: true,
      });
    }

    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
          ...this.defaultHeaders,
          ...(init.headers as Record<string, string> | undefined),
        },
      });

      const contentType = res.headers.get('content-type') ?? '';
      const isJson = contentType.includes('application/json');
      const body = isJson ? await res.json() : await res.text();

      if (!res.ok) {
        throw new ApiError(
          `API ${res.status} ${res.statusText}`,
          res.status,
          body,
        );
      }
      return body as T;
    } catch (err) {
      this.onError?.(err, context);
      throw err;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  /** ---------- Публичные методы API ---------- */

  /** GET /health */
  health(signal?: AbortSignal): Promise<{ status: string }> {
    return this.request('/health', { method: 'GET', signal }, 'health');
  }

  /** POST /api/v1/jobs/demo */
  createDemoJob(
    params: DemoJobParams,
    signal?: AbortSignal,
  ): Promise<Job> {
    return this.request<Job>(
      '/api/v1/jobs/demo',
      {
        method: 'POST',
        signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      },
      'createDemoJob',
    );
  }

  /** POST /api/v1/jobs/upload */
  uploadJob(
    file: File | Blob,
    params: UploadJobParams = {},
    signal?: AbortSignal,
  ): Promise<Job> {
    const form = new FormData();
    form.append('file', file);
    (Object.keys(params) as (keyof UploadJobParams)[]).forEach((key) => {
      const value = params[key];
      if (value !== undefined && value !== null) {
        form.append(key, String(value));
      }
    });

    return this.request<Job>(
      '/api/v1/jobs/upload',
      { method: 'POST', signal, body: form },
      'uploadJob',
    );
  }

  /** GET /api/v1/jobs/{job_id} */
  getJob(jobId: string, signal?: AbortSignal): Promise<Job> {
    return this.request<Job>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}`,
      { method: 'GET', signal },
      'getJob',
    );
  }

  /** GET /api/v1/jobs — список задач текущего процесса */
  listJobs(signal?: AbortSignal): Promise<Job[]> {
    return this.request<Job[]>('/api/v1/jobs', { method: 'GET', signal }, 'listJobs');
  }

  /** GET /api/v1/jobs/{job_id}/result — вернуть blob для скачивания */
  async downloadResult(jobId: string, signal?: AbortSignal): Promise<Blob> {
    const res = await fetch(
      `${this.baseUrl}/api/v1/jobs/${encodeURIComponent(jobId)}/result`,
      {
        method: 'GET',
        signal,
        headers: { ...this.defaultHeaders },
      },
    );
    if (!res.ok) {
      const body = await res.text().catch(() => null);
      throw new ApiError(
        `Download failed ${res.status} ${res.statusText}`,
        res.status,
        body,
      );
    }
    return res.blob();
  }

  /** Скачать результат и спровоцировать сохранение файла в браузере. */
  async saveResultAsFile(
    jobId: string,
    filename = `schedule-${jobId}.xlsx`,
    signal?: AbortSignal,
  ): Promise<void> {
    const blob = await this.downloadResult(jobId, signal);
    const url = URL.createObjectURL(blob);
    try {
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } finally {
      // Дадим браузеру время начать загрузку
      setTimeout(() => URL.revokeObjectURL(url), 1_000);
    }
  }

  /**
   * Поллинг статуса задачи до completed/failed.
   * Возвращает финальный Job либо бросает ошибку по таймауту/abort.
   */
  async waitForJob(
    jobId: string,
    options: {
      intervalMs?: number;
      timeoutMs?: number;
      signal?: AbortSignal;
      onUpdate?: (job: Job) => void;
    } = {},
  ): Promise<Job> {
    const intervalMs = options.intervalMs ?? 2_000;
    const timeoutMs = options.timeoutMs ?? 30 * 60_000; // 30 минут
    const startedAt = Date.now();

    // eslint-disable-next-line no-constant-condition
    while (true) {
      if (options.signal?.aborted) {
        throw new DOMException('Aborted', 'AbortError');
      }
      const job = await this.getJob(jobId, options.signal);
      options.onUpdate?.(job);

      if (job.status === 'completed') return job;
      if (job.status === 'failed') {
        throw new ApiError(
          job.error ?? 'Job failed',
          500,
          job,
        );
      }
      if (Date.now() - startedAt > timeoutMs) {
        throw new ApiError('Job polling timeout', 408, job);
      }
      await new Promise<void>((resolve) => setTimeout(resolve, intervalMs));
    }
  }
}

/** Удобный шорткат — сразу получить готовый синглтон. */
export const api = ApiService.getInstance();
