import { useCallback, useEffect, useRef, useState } from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import GlassPanel from "./components/GlassPanel/GlassPanel";
import Sidebar from "./components/Sidebar/Sidebar";
import { api, ApiError, type Job, type DemoJobParams } from "./services/ApiService";
import "./index.css";

/* ------------------------------------------------------------------ */
/*  Общие хелперы                                                      */
/* ------------------------------------------------------------------ */

function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

function formatTime(iso?: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString();
}

const STATUS_LABEL: Record<string, string> = {
  pending: "в очереди",
  running: "выполняется",
  completed: "готово",
  failed: "ошибка",
};

/* ------------------------------------------------------------------ */
/*  Страница: главная — демо-задача                                    */
/* ------------------------------------------------------------------ */

function HomePage() {
  const [params, setParams] = useState<DemoJobParams>({
    n_teachers: 30,
    n_groups: 20,
    n_rooms: 20,
    pop_size: 40,
    generations: 100,
    elite: 4,
    workers: 4,
  });
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const update = <K extends keyof DemoJobParams>(key: K, value: number) => {
    setParams((p) => ({ ...p, [key]: value }));
  };

  const startDemo = async () => {
    setBusy(true);
    setError(null);
    setJob(null);
    abortRef.current = new AbortController();

    try {
      const created = await api.createDemoJob(params, abortRef.current.signal);
      setJob(created);

      const finished = await api.waitForJob(created.job_id, {
        signal: abortRef.current.signal,
        intervalMs: 1_500,
        onUpdate: setJob,
      });
      setJob(finished);

      await api.saveResultAsFile(finished.job_id);
    } catch (e) {
      if ((e as DOMException)?.name !== "AbortError") {
        setError(e instanceof ApiError ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="demo-page">
      <h2>Демонстрационная генерация</h2>
      <p className="muted">
        Создаёт синтетические данные и запускает генетический алгоритм на сервере.
      </p>

      <div className="form-grid">
        {(
          [
            ["n_teachers", "Преподаватели"],
            ["n_groups", "Группы"],
            ["n_rooms", "Аудитории"],
            ["pop_size", "Размер популяции"],
            ["generations", "Поколения"],
            ["elite", "Элита"],
            ["workers", "GA workers"],
          ] as [keyof DemoJobParams, string][]
        ).map(([key, label]) => (
          <label key={key} className="field">
            <span>{label}</span>
            <input
              type="number"
              min={1}
              value={params[key]}
              onChange={(e) => update(key, Number(e.target.value))}
              disabled={busy}
            />
          </label>
        ))}
      </div>

      <div className="actions">
        <button onClick={startDemo} disabled={busy}>
          {busy ? "Генерация…" : "Сгенерировать демо"}
        </button>
        {busy && (
          <button
            className="secondary"
            onClick={() => abortRef.current?.abort()}
          >
            Прервать ожидание
          </button>
        )}
      </div>

      {job && <JobCard job={job} />}
      {error && <p className="error">{error}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Страница: загрузка Excel / ZIP                                     */
/* ------------------------------------------------------------------ */

function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [popSize, setPopSize] = useState(60);
  const [generations, setGenerations] = useState(300);
  const [workers, setWorkers] = useState(4);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const handleUpload = async () => {
    if (!file) {
      setError("Выберите файл .xlsx / .xlsm или .zip с CSV");
      return;
    }
    setBusy(true);
    setError(null);
    setJob(null);
    abortRef.current = new AbortController();

    try {
      const created = await api.uploadJob(
        file,
        { pop_size: popSize, generations, workers },
        abortRef.current.signal,
      );
      setJob(created);

      const finished = await api.waitForJob(created.job_id, {
        signal: abortRef.current.signal,
        intervalMs: 2_000,
        onUpdate: setJob,
      });
      setJob(finished);
      await api.saveResultAsFile(finished.job_id);
    } catch (e) {
      if ((e as DOMException)?.name !== "AbortError") {
        setError(e instanceof ApiError ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="upload-page">
      <h2>Загрузка исходных данных</h2>
      <p className="muted">
        Поддерживается <code>.xlsx</code>, <code>.xlsm</code> или ZIP с CSV:
        Преподаватели.csv, Группы.csv, Аудитории.csv, Нагрузка.csv.
      </p>

      <div className="form-grid">
        <label className="field field--wide">
          <span>Файл</span>
          <input
            type="file"
            accept=".xlsx,.xlsm,.zip"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            disabled={busy}
          />
        </label>
        <label className="field">
          <span>Размер популяции</span>
          <input
            type="number"
            min={2}
            value={popSize}
            onChange={(e) => setPopSize(Number(e.target.value))}
            disabled={busy}
          />
        </label>
        <label className="field">
          <span>Поколения</span>
          <input
            type="number"
            min={1}
            value={generations}
            onChange={(e) => setGenerations(Number(e.target.value))}
            disabled={busy}
          />
        </label>
        <label className="field">
          <span>GA workers</span>
          <input
            type="number"
            min={1}
            value={workers}
            onChange={(e) => setWorkers(Number(e.target.value))}
            disabled={busy}
          />
        </label>
      </div>

      <div className="actions">
        <button onClick={handleUpload} disabled={busy || !file}>
          {busy ? "Выполняется…" : "Загрузить и запустить"}
        </button>
        {busy && (
          <button
            className="secondary"
            onClick={() => abortRef.current?.abort()}
          >
            Прервать ожидание
          </button>
        )}
      </div>

      {job && <JobCard job={job} />}
      {error && <p className="error">{error}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Страница: список задач                                             */
/* ------------------------------------------------------------------ */

function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const now = useNow(2_000);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setJobs(await api.listJobs());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5_000);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <div className="jobs-page">
      <div className="row-between">
        <h2>Задачи текущего процесса</h2>
        <button onClick={refresh} disabled={loading}>
          {loading ? "Обновление…" : "Обновить"}
        </button>
      </div>
      <p className="muted">
        Реестр хранится в памяти backend — после перезапуска API список пуст.
        Автообновление каждые 5 с (последнее: {new Date(now).toLocaleTimeString()}).
      </p>

      {error && <p className="error">{error}</p>}

      {jobs.length === 0 ? (
        <p className="muted">Задач пока нет.</p>
      ) : (
        <table className="jobs-table">
          <thead>
            <tr>
              <th>job_id</th>
              <th>Статус</th>
              <th>Создана</th>
              <th>Завершена</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.job_id}>
                <td className="mono">{j.job_id.slice(0, 8)}…</td>
                <td>
                  <span className={`badge badge--${j.status}`}>
                    {STATUS_LABEL[j.status] ?? j.status}
                  </span>
                </td>
                <td>{formatTime(j.created_at)}</td>
                <td>{formatTime(j.finished_at)}</td>
                <td>
                  {j.status === "completed" ? (
                    <button
                      className="small"
                      onClick={() => api.saveResultAsFile(j.job_id)}
                    >
                      Скачать
                    </button>
                  ) : j.error ? (
                    <span className="error-inline">{j.error}</span>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Страница: health-check                                             */
/* ------------------------------------------------------------------ */

function HealthPage() {
  const [status, setStatus] = useState<string>("—");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const check = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.health();
      setStatus(res.status ?? "ok");
    } catch (e) {
      setStatus("недоступен");
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    check();
  }, []);

  return (
    <div>
      <h2>Состояние API</h2>
      <p>
        Статус: <strong>{status}</strong>{" "}
        <button className="small" onClick={check} disabled={loading}>
          {loading ? "…" : "Проверить"}
        </button>
      </p>
      {error && <p className="error">{error}</p>}
      <p className="muted">
        Ожидается <code>GET /health</code> → <code>{`{ "status": "ok" }`}</code>.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Переиспользуемая карточка задачи                                   */
/* ------------------------------------------------------------------ */

function JobCard({ job }: { job: Job }) {
  const inProgress = job.status === "pending" || job.status === "running";
  return (
    <div className="job-card">
      <div className="job-card__head">
        <span className={`badge badge--${job.status}`}>
          {STATUS_LABEL[job.status] ?? job.status}
        </span>
        <span className="mono">id: {job.job_id}</span>
      </div>

      <dl className="job-card__meta">
        <div>
          <dt>Создана</dt>
          <dd>{formatTime(job.created_at)}</dd>
        </div>
        <div>
          <dt>Начата</dt>
          <dd>{formatTime(job.started_at)}</dd>
        </div>
        <div>
          <dt>Завершена</dt>
          <dd>{formatTime(job.finished_at)}</dd>
        </div>
      </dl>

      {job.metrics && (
        <>
          <h4>Метрики</h4>
          <pre className="metrics">{JSON.stringify(job.metrics, null, 2)}</pre>
        </>
      )}

      {job.error && <p className="error">{job.error}</p>}

      {inProgress && (
        <div className="progress">
          <div className="progress__bar" />
          <span>Ожидание завершения…</span>
        </div>
      )}

      {job.status === "completed" && (
        <button onClick={() => api.saveResultAsFile(job.job_id)}>
          Скачать schedule.xlsx
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Корневой компонент                                                 */
/* ------------------------------------------------------------------ */

export function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Sidebar />

        <main className="app__content">
          <Routes>
            <Route
              path="/"
              element={
                <GlassPanel title="главная — демо-генерация">
                  <HomePage />
                </GlassPanel>
              }
            />
            <Route
              path="/upload"
              element={
                <GlassPanel title="загрузка данных">
                  <UploadPage />
                </GlassPanel>
              }
            />
            <Route
              path="/jobs"
              element={
                <GlassPanel title="задачи">
                  <JobsPage />
                </GlassPanel>
              }
            />
            <Route
              path="/health"
              element={
                <GlassPanel title="health-check">
                  <HealthPage />
                </GlassPanel>
              }
            />
            <Route
              path="/auth"
              element={
                <GlassPanel title="вход">
                  <p>Форма авторизации (заглушка).</p>
                  <p className="muted">
                    <Link to="/">← вернуться на главную</Link>
                  </p>
                </GlassPanel>
              }
            />
            <Route
              path="*"
              element={
                <GlassPanel title="404">
                  <p>Страница не найдена.</p>
                  <Link to="/">На главную</Link>
                </GlassPanel>
              }
            />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
