"use client";
import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { api, Task } from "@/lib/api";
import { RefreshCw, Trash2 } from "lucide-react";

// Client-side task history stored in localStorage
function getLocalTasks(): string[] {
  if (typeof window === "undefined") return [];
  return JSON.parse(localStorage.getItem("opensway_tasks") || "[]");
}

function StatusBadge({ status }: { status: Task["status"] }) {
  const cls = `badge badge-${status.toLowerCase()}`;
  const dot = status === "RUNNING" ? "animate-pulse " : "";
  return <span className={cls}><span className={`${dot}w-1.5 h-1.5 rounded-full bg-current`} />{status}</span>;
}

function TaskRow({ taskId, onRemove }: { taskId: string; onRemove: (id: string) => void }) {
  const { data: task, isLoading, mutate } = useSWR<Task>(
    `/v1/tasks/${taskId}`,
    (url) => api.get(url),
    { refreshInterval: (data) => data?.status === "RUNNING" || data?.status === "PENDING" ? 3000 : 0 }
  );

  if (isLoading) return <tr><td colSpan={5} className="py-3 px-4 text-zinc-500 text-sm">Loading…</td></tr>;
  if (!task) return null;

  return (
    <tr className="border-b border-zinc-800 hover:bg-zinc-900/50 transition-colors">
      <td className="py-3 px-4">
        <Link href={`/tasks/${task.id}`} className="font-mono text-xs text-indigo-400 hover:underline">
          {task.id.slice(0, 8)}…
        </Link>
      </td>
      <td className="py-3 px-4"><StatusBadge status={task.status} /></td>
      <td className="py-3 px-4">
        {task.progress !== undefined && (
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-zinc-800 rounded-full h-1.5">
              <div className="bg-indigo-500 h-1.5 rounded-full transition-all"
                style={{ width: `${(task.progress * 100).toFixed(0)}%` }} />
            </div>
            <span className="text-xs text-zinc-400">{(task.progress * 100).toFixed(0)}%</span>
          </div>
        )}
      </td>
      <td className="py-3 px-4 text-xs text-zinc-400">
        {task.createdAt ? new Date(task.createdAt).toLocaleString() : "—"}
      </td>
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <button onClick={() => mutate()} title="Refresh"
            className="text-zinc-500 hover:text-zinc-200 transition-colors">
            <RefreshCw size={14} />
          </button>
          <button onClick={() => onRemove(task.id)} title="Remove from list"
            className="text-zinc-500 hover:text-red-400 transition-colors">
            <Trash2 size={14} />
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function TasksPage() {
  const [taskIds, setTaskIds] = useState<string[]>(getLocalTasks);

  function removeTask(id: string) {
    const updated = taskIds.filter((t) => t !== id);
    setTaskIds(updated);
    localStorage.setItem("opensway_tasks", JSON.stringify(updated));
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Tasks</h1>
        <p className="text-zinc-400 text-sm mt-1">All generation jobs from this browser session</p>
      </div>

      {taskIds.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-zinc-400">No tasks yet.</p>
          <Link href="/generate" className="mt-3 inline-block text-indigo-400 hover:underline text-sm">
            Start generating →
          </Link>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-left text-xs text-zinc-400">
                <th className="py-3 px-4">Task ID</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 w-40">Progress</th>
                <th className="py-3 px-4">Created</th>
                <th className="py-3 px-4" />
              </tr>
            </thead>
            <tbody>
              {taskIds.map((id) => (
                <TaskRow key={id} taskId={id} onRemove={removeTask} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
