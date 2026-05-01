import React from "react";
import ReactDOM from "react-dom/client";
import { CalendarDays, CheckCircle2, Circle, Clock3, ExternalLink, Loader2, MoveRight, RefreshCcw, ShieldCheck } from "lucide-react";
import clsx from "clsx";
import "./styles.css";

type MissionUser = {
  id: number;
  email: string;
  firstName?: string;
  lastName?: string;
};

type TaskStatus = "open" | "in_progress" | "on_hold" | "done";
type WritableTaskStatus = "open" | "in_progress" | "done";
type BoardColumn = "backlog" | "inProgress" | "done";

type Task = {
  id: string;
  text: string;
  description?: string | null;
  priority?: number | null;
  completion_status: TaskStatus;
  due_date?: string | null;
  due_time?: string | null;
  topic?: string | null;
  subtopic?: string | null;
  entity_name?: string | null;
  entity_type?: string | null;
  created_at?: string | null;
  completed_at?: string | null;
  record_name?: string | null;
};

type CalendarEvent = {
  id: string;
  source_type: "legacy" | "batch";
  source_table: string;
  summary: string;
  description?: string | null;
  location?: string | null;
  start_datetime: string;
  end_datetime?: string | null;
  timezone?: string | null;
  status?: string | null;
  error_message?: string | null;
  html_link?: string | null;
};

type BootstrapPayload = {
  user: MissionUser | null;
  tasks: Task[];
  calendarEvents: CalendarEvent[];
  timezone: string;
};

type RootConfig = {
  bootstrapUrl: string;
  tasksUrl: string;
  calendarUrl: string;
  taskStatusUrlTemplate: string;
};

const columns: Array<{
  id: BoardColumn;
  title: string;
  writeStatus: WritableTaskStatus;
  readStatuses: TaskStatus[];
  accent: string;
}> = [
  {
    id: "backlog",
    title: "Backlog",
    writeStatus: "open",
    readStatuses: ["open"],
    accent: "from-cyan-400 to-blue-500",
  },
  {
    id: "inProgress",
    title: "In Progress",
    writeStatus: "in_progress",
    readStatuses: ["in_progress", "on_hold"],
    accent: "from-violet-400 to-fuchsia-500",
  },
  {
    id: "done",
    title: "Done",
    writeStatus: "done",
    readStatuses: ["done"],
    accent: "from-emerald-400 to-teal-500",
  },
];

function getCookie(name: string): string {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return decodeURIComponent(parts.pop()?.split(";").shift() ?? "");
  }
  return "";
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function statusToColumn(status: TaskStatus): BoardColumn {
  if (status === "done") return "done";
  if (status === "in_progress" || status === "on_hold") return "inProgress";
  return "backlog";
}

function formatDate(value?: string | null): string {
  if (!value) return "No date";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function formatDateTime(value?: string | null): string {
  if (!value) return "No time";
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatTime(value?: string | null): string {
  if (!value) return "";
  return value.slice(0, 5);
}

function priorityLabel(priority?: number | null): string {
  if (!priority) return "Normal";
  if (priority >= 5) return "Urgent";
  if (priority >= 4) return "High";
  if (priority <= 2) return "Low";
  return "Normal";
}

function App({ config }: { config: RootConfig }) {
  const [activeScreen, setActiveScreen] = React.useState<"tasks" | "calendar">("tasks");
  const [user, setUser] = React.useState<MissionUser | null>(null);
  const [tasks, setTasks] = React.useState<Task[]>([]);
  const [calendarEvents, setCalendarEvents] = React.useState<CalendarEvent[]>([]);
  const [timezone, setTimezone] = React.useState("Europe/Lisbon");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [movingTaskId, setMovingTaskId] = React.useState<string | null>(null);

  const loadBootstrap = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchJson<BootstrapPayload>(config.bootstrapUrl);
      setUser(payload.user);
      setTasks(payload.tasks);
      setCalendarEvents(payload.calendarEvents);
      setTimezone(payload.timezone || "Europe/Lisbon");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mission Control failed to load.");
    } finally {
      setLoading(false);
    }
  }, [config.bootstrapUrl]);

  React.useEffect(() => {
    void loadBootstrap();
  }, [loadBootstrap]);

  async function moveTask(taskId: string, status: WritableTaskStatus) {
    setMovingTaskId(taskId);
    setError(null);
    const previousTasks = tasks;
    setTasks((current) =>
      current.map((task) =>
        task.id === taskId ? { ...task, completion_status: status } : task,
      ),
    );

    try {
      const url = config.taskStatusUrlTemplate.replace("__TASK_ID__", taskId);
      const payload = await fetchJson<{ task: Task }>(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({ completionStatus: status }),
      });
      setTasks((current) =>
        current.map((task) => (task.id === taskId ? payload.task : task)),
      );
    } catch (err) {
      setTasks(previousTasks);
      setError(err instanceof Error ? err.message : "Task movement failed.");
    } finally {
      setMovingTaskId(null);
    }
  }

  const counts = React.useMemo(() => {
    return columns.reduce<Record<BoardColumn, number>>(
      (acc, column) => {
        acc[column.id] = tasks.filter((task) =>
          column.readStatuses.includes(task.completion_status),
        ).length;
        return acc;
      },
      { backlog: 0, inProgress: 0, done: 0 },
    );
  }, [tasks]);

  return (
    <main className="min-h-screen overflow-hidden bg-[#050816] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(124,58,237,0.25),transparent_32%),radial-gradient(circle_at_90%_0%,rgba(34,211,238,0.2),transparent_26%),linear-gradient(135deg,rgba(15,23,42,0),rgba(15,23,42,0.8))]" />
      <div className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-5 py-5 lg:px-8">
        <Header
          activeScreen={activeScreen}
          onScreenChange={setActiveScreen}
          user={user}
          onRefresh={loadBootstrap}
          loading={loading}
        />

        {error ? <Alert message={error} /> : null}

        <StatsBar counts={counts} calendarCount={calendarEvents.length} timezone={timezone} />

        {loading ? (
          <LoadingPanel />
        ) : activeScreen === "tasks" ? (
          <TasksBoard tasks={tasks} counts={counts} movingTaskId={movingTaskId} onMoveTask={moveTask} />
        ) : (
          <CalendarScreen events={calendarEvents} timezone={timezone} />
        )}
      </div>
    </main>
  );
}

function Header({
  activeScreen,
  onScreenChange,
  user,
  onRefresh,
  loading,
}: {
  activeScreen: "tasks" | "calendar";
  onScreenChange: (screen: "tasks" | "calendar") => void;
  user: MissionUser | null;
  onRefresh: () => void;
  loading: boolean;
}) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.04] p-4 shadow-glow backdrop-blur">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.45em] text-cyan-200/70">UTTDTY</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">Mission Control</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">
            Logged-in command center for tasks, calendar signals, and operational focus.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-100">
            <ShieldCheck className="mr-2 inline size-4" />
            Django session active
          </div>
          <div className="rounded-full border border-white/10 bg-slate-950/50 px-3 py-2 text-xs text-slate-300">
            {user?.email ?? "No active user selected"}
          </div>
          <nav className="rounded-full border border-white/10 bg-slate-950/70 p-1">
            {(["tasks", "calendar"] as const).map((screen) => (
              <button
                key={screen}
                type="button"
                className={clsx(
                  "rounded-full px-4 py-2 text-sm font-medium capitalize transition",
                  activeScreen === screen
                    ? "bg-violet-500 text-white shadow-lg shadow-violet-950/50"
                    : "text-slate-400 hover:text-white",
                )}
                onClick={() => onScreenChange(screen)}
              >
                {screen}
              </button>
            ))}
          </nav>
          <button
            type="button"
            className="rounded-full border border-white/10 bg-white/[0.04] p-2 text-slate-300 transition hover:border-cyan-300/40 hover:text-white"
            onClick={onRefresh}
            disabled={loading}
            aria-label="Refresh Mission Control"
          >
            <RefreshCcw className={clsx("size-4", loading && "animate-spin")} />
          </button>
        </div>
      </div>
    </section>
  );
}

function StatsBar({
  counts,
  calendarCount,
  timezone,
}: {
  counts: Record<BoardColumn, number>;
  calendarCount: number;
  timezone: string;
}) {
  const total = counts.backlog + counts.inProgress + counts.done;
  const donePercent = total ? Math.round((counts.done / total) * 100) : 0;
  return (
    <section className="grid gap-4 lg:grid-cols-[1.1fr_1fr_1fr_1fr]">
      <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
        <div className="flex items-center gap-4">
          <div
            className="grid size-16 place-items-center rounded-full"
            style={{
              background: `conic-gradient(#34d399 ${donePercent}%, #22d3ee ${donePercent}% ${Math.min(donePercent + 30, 100)}%, rgba(148,163,184,0.18) 0)`,
            }}
          >
            <div className="size-10 rounded-full bg-[#050816]" />
          </div>
          <div>
            <p className="text-sm text-slate-400">Task completion</p>
            <p className="text-2xl font-semibold">{donePercent}%</p>
            <p className="text-xs text-slate-500">{total} visible tasks</p>
          </div>
        </div>
      </div>
      <Metric title="Backlog" value={counts.backlog} tone="cyan" />
      <Metric title="In Progress" value={counts.inProgress} tone="violet" />
      <Metric title="Calendar Window" value={calendarCount} suffix={`events · ${timezone}`} tone="amber" />
    </section>
  );
}

function Metric({
  title,
  value,
  suffix,
  tone,
}: {
  title: string;
  value: number;
  suffix?: string;
  tone: "cyan" | "violet" | "amber";
}) {
  const tones = {
    cyan: "text-cyan-200 border-cyan-300/20 bg-cyan-300/10",
    violet: "text-violet-200 border-violet-300/20 bg-violet-300/10",
    amber: "text-amber-200 border-amber-300/20 bg-amber-300/10",
  };
  return (
    <div className={clsx("rounded-2xl border p-4", tones[tone])}>
      <p className="text-xs uppercase tracking-[0.25em] opacity-70">{title}</p>
      <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
      <p className="mt-1 text-xs opacity-70">{suffix ?? "tasks"}</p>
    </div>
  );
}

function Alert({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
      {message}
    </div>
  );
}

function LoadingPanel() {
  return (
    <div className="grid min-h-[420px] place-items-center rounded-3xl border border-white/10 bg-slate-950/40">
      <div className="flex items-center gap-3 text-slate-300">
        <Loader2 className="size-5 animate-spin text-cyan-300" />
        Loading real Mission Control data
      </div>
    </div>
  );
}

function TasksBoard({
  tasks,
  counts,
  movingTaskId,
  onMoveTask,
}: {
  tasks: Task[];
  counts: Record<BoardColumn, number>;
  movingTaskId: string | null;
  onMoveTask: (taskId: string, status: WritableTaskStatus) => Promise<void>;
}) {
  const [draggedTaskId, setDraggedTaskId] = React.useState<string | null>(null);

  return (
    <section className="grid gap-4 lg:grid-cols-3">
      {columns.map((column) => {
        const columnTasks = tasks.filter((task) => statusToColumn(task.completion_status) === column.id);
        return (
          <div
            key={column.id}
            className="min-h-[520px] rounded-3xl border border-white/10 bg-slate-950/50 p-4 backdrop-blur"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const taskId = event.dataTransfer.getData("text/plain") || draggedTaskId;
              if (taskId) {
                void onMoveTask(taskId, column.writeStatus);
              }
              setDraggedTaskId(null);
            }}
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={clsx("h-8 w-1 rounded-full bg-gradient-to-b", column.accent)} />
                <div>
                  <h2 className="font-semibold text-white">{column.title}</h2>
                  <p className="text-xs text-slate-500">{counts[column.id]} cards</p>
                </div>
              </div>
              <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-slate-400">
                {counts[column.id]}
              </span>
            </div>
            <div className="space-y-3">
              {columnTasks.length ? (
                columnTasks.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    moving={movingTaskId === task.id}
                    onDragStart={() => setDraggedTaskId(task.id)}
                    onMoveTask={onMoveTask}
                  />
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
                  No tasks in this lane.
                </div>
              )}
            </div>
          </div>
        );
      })}
    </section>
  );
}

function TaskCard({
  task,
  moving,
  onDragStart,
  onMoveTask,
}: {
  task: Task;
  moving: boolean;
  onDragStart: () => void;
  onMoveTask: (taskId: string, status: WritableTaskStatus) => Promise<void>;
}) {
  const currentColumn = statusToColumn(task.completion_status);
  return (
    <article
      draggable
      onDragStart={(event) => {
        event.dataTransfer.setData("text/plain", task.id);
        onDragStart();
      }}
      className={clsx(
        "rounded-2xl border border-white/10 bg-white/[0.045] p-4 shadow-lg shadow-black/20 transition hover:border-cyan-300/30 hover:bg-white/[0.07]",
        moving && "opacity-60",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold leading-6 text-white">{task.text}</h3>
          {task.description ? (
            <p className="mt-2 line-clamp-3 text-xs leading-5 text-slate-400">{task.description}</p>
          ) : null}
        </div>
        {task.completion_status === "done" ? (
          <CheckCircle2 className="size-4 shrink-0 text-emerald-300" />
        ) : (
          <Circle className="size-4 shrink-0 text-slate-500" />
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Pill tone={task.priority && task.priority >= 4 ? "red" : "blue"}>{priorityLabel(task.priority)}</Pill>
        {task.topic ? <Pill tone="violet">{task.topic}</Pill> : null}
        {task.subtopic ? <Pill tone="slate">{task.subtopic}</Pill> : null}
        {task.entity_name ? <Pill tone="green">{task.entity_name}</Pill> : null}
      </div>
      <div className="mt-4 grid gap-2 text-xs text-slate-500">
        <div className="flex items-center justify-between">
          <span>Due</span>
          <span className="text-slate-300">
            {formatDate(task.due_date)} {formatTime(task.due_time)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span>Created</span>
          <span className="text-slate-300">{task.created_at ? formatDateTime(task.created_at) : "Unknown"}</span>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2 border-t border-white/10 pt-3">
        {columns
          .filter((column) => column.id !== currentColumn)
          .map((column) => (
            <button
              key={column.id}
              type="button"
              className="inline-flex items-center gap-1 rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300 transition hover:border-cyan-300/40 hover:text-white disabled:opacity-50"
              disabled={moving}
              onClick={() => void onMoveTask(task.id, column.writeStatus)}
            >
              Move to {column.title}
              <MoveRight className="size-3" />
            </button>
          ))}
      </div>
    </article>
  );
}

function Pill({ children, tone }: { children: React.ReactNode; tone: "red" | "blue" | "violet" | "slate" | "green" }) {
  const tones = {
    red: "border-red-300/20 bg-red-400/10 text-red-100",
    blue: "border-blue-300/20 bg-blue-400/10 text-blue-100",
    violet: "border-violet-300/20 bg-violet-400/10 text-violet-100",
    slate: "border-slate-300/20 bg-slate-400/10 text-slate-200",
    green: "border-emerald-300/20 bg-emerald-400/10 text-emerald-100",
  };
  return <span className={clsx("rounded-full border px-2 py-1 text-[11px]", tones[tone])}>{children}</span>;
}

function CalendarScreen({ events, timezone }: { events: CalendarEvent[]; timezone: string }) {
  const grouped = React.useMemo(() => {
    return events.reduce<Record<string, CalendarEvent[]>>((acc, event) => {
      const key = new Intl.DateTimeFormat(undefined, {
        weekday: "long",
        month: "short",
        day: "numeric",
        timeZone: event.timezone || timezone,
      }).format(new Date(event.start_datetime));
      acc[key] = [...(acc[key] ?? []), event];
      return acc;
    }, {});
  }, [events, timezone]);

  return (
    <section className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
      <div className="rounded-3xl border border-white/10 bg-slate-950/50 p-5">
        <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Calendar Scope</p>
        <h2 className="mt-2 text-2xl font-semibold">Today and Tomorrow</h2>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          Showing legacy confirmed calendar entries and generated batch events for the current operational window.
        </p>
        <div className="mt-6 space-y-3">
          <SourceLegend label="Legacy confirmed events" tone="green" />
          <SourceLegend label="Batch generated events" tone="violet" />
          <SourceLegend label={`Timezone: ${timezone}`} tone="blue" />
        </div>
      </div>
      <div className="space-y-4">
        {events.length ? (
          Object.entries(grouped).map(([day, dayEvents]) => (
            <div key={day} className="rounded-3xl border border-white/10 bg-slate-950/50 p-4">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="font-semibold text-white">{day}</h3>
                <span className="rounded-full border border-white/10 px-2 py-1 text-xs text-slate-400">
                  {dayEvents.length} events
                </span>
              </div>
              <div className="space-y-3">
                {dayEvents.map((event) => (
                  <CalendarCard key={`${event.source_type}-${event.id}`} event={event} />
                ))}
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/50 p-10 text-center text-slate-400">
            <CalendarDays className="mx-auto mb-3 size-8 text-cyan-300" />
            No calendar entries for today or tomorrow.
          </div>
        )}
      </div>
    </section>
  );
}

function SourceLegend({ label, tone }: { label: string; tone: "green" | "violet" | "blue" }) {
  const tones = {
    green: "bg-emerald-300",
    violet: "bg-violet-300",
    blue: "bg-cyan-300",
  };
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-3 text-sm text-slate-300">
      <span className={clsx("size-2 rounded-full", tones[tone])} />
      {label}
    </div>
  );
}

function CalendarCard({ event }: { event: CalendarEvent }) {
  const isFailed = event.status === "failed";
  const sourceTone = event.source_type === "legacy" ? "green" : "violet";
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-2 flex flex-wrap gap-2">
            <Pill tone={sourceTone}>{event.source_type === "legacy" ? "confirmed" : "batch"}</Pill>
            {event.status ? <Pill tone={isFailed ? "red" : "blue"}>{event.status}</Pill> : null}
          </div>
          <h3 className="font-semibold text-white">{event.summary || "Untitled event"}</h3>
          {event.description ? <p className="mt-2 text-sm leading-6 text-slate-400">{event.description}</p> : null}
          {event.location ? <p className="mt-2 text-xs text-slate-500">{event.location}</p> : null}
        </div>
        {event.html_link ? (
          <a
            href={event.html_link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-full border border-white/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:border-cyan-300/40"
          >
            Open
            <ExternalLink className="size-3" />
          </a>
        ) : null}
      </div>
      <div className="mt-4 grid gap-2 border-t border-white/10 pt-3 text-xs text-slate-500 sm:grid-cols-2">
        <span className="flex items-center gap-2">
          <Clock3 className="size-3 text-cyan-300" />
          {formatDateTime(event.start_datetime)}
        </span>
        <span>{event.end_datetime ? `Ends ${formatDateTime(event.end_datetime)}` : "No end time"}</span>
        <span>{event.timezone || "No timezone"}</span>
        <span>{event.source_table}</span>
      </div>
      {event.error_message ? (
        <div className="mt-3 rounded-xl border border-red-400/20 bg-red-500/10 px-3 py-2 text-xs text-red-100">
          {event.error_message}
        </div>
      ) : null}
    </article>
  );
}

const rootElement = document.getElementById("mission-control-root");

if (rootElement) {
  const config: RootConfig = {
    bootstrapUrl: rootElement.dataset.bootstrapUrl ?? "/mission-control/api/bootstrap/",
    tasksUrl: rootElement.dataset.tasksUrl ?? "/mission-control/api/tasks/",
    calendarUrl: rootElement.dataset.calendarUrl ?? "/mission-control/api/calendar/",
    taskStatusUrlTemplate:
      rootElement.dataset.taskStatusUrlTemplate ?? "/mission-control/api/tasks/__TASK_ID__/status/",
  };

  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App config={config} />
    </React.StrictMode>,
  );
}
