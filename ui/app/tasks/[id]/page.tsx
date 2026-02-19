"use client";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { api, Task } from "@/lib/api";
import { ArrowLeft, Download } from "lucide-react";
import Link from "next/link";
import dynamic from "next/dynamic";

const ReactPlayer = dynamic(() => import("react-player/lazy"), { ssr: false });

function StatusBadge({ status }: { status: Task["status"] }) {
  const cls = `badge badge-${status.toLowerCase()}`;
  const dot = status === "RUNNING" ? "animate-pulse " : "";
  return <span className={`text-base ${cls}`}><span className={`${dot}w-2 h-2 rounded-full bg-current`} />{status}</span>;
}

function OutputViewer({ urls }: { urls: string[] }) {
  if (!urls?.length) return null;
  const url = urls[0];
  const isVideo = url.match(/\.(mp4|webm|mov)(\?|$)/i);
  const isAudio = url.match(/\.(wav|mp3|ogg|flac)(\?|$)/i);
  const isImage = url.match(/\.(png|jpg|jpeg|gif|webp)(\?|$)/i);

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Output</h2>
        <a href={url} download
          className="flex items-center gap-1.5 text-sm text-indigo-400 hover:text-indigo-300">
          <Download size={14} /> Download
        </a>
      </div>
      {isVideo && (
        <div className="rounded-lg overflow-hidden bg-black">
          <ReactPlayer url={url} controls width="100%" height="auto" />
        </div>
      )}
      {isAudio && (
        <audio controls className="w-full" src={url}>
          Your browser does not support audio playback.
        </audio>
      )}
      {isImage && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt="Generated output"
          className="rounded-lg max-w-full max-h-[600px] object-contain" />
      )}
      <p className="font-mono text-xs text-zinc-500 break-all">{url}</p>
    </div>
  );
}

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: task, isLoading } = useSWR<Task>(
    `/v1/tasks/${id}`,
    (url) => api.get(url),
    { refreshInterval: (data) => !data || data.status === "RUNNING" || data.status === "PENDING" ? 2000 : 0 }
  );

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-3">
        <Link href="/tasks" className="text-zinc-400 hover:text-zinc-100">
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-xl font-bold font-mono">{id}</h1>
          <p className="text-zinc-400 text-sm">Task detail</p>
        </div>
      </div>

      {isLoading && <p className="text-zinc-400">Loading…</p>}

      {task && (
        <>
          <div className="card space-y-4">
            <div className="flex items-center justify-between">
              <StatusBadge status={task.status} />
              {task.progress !== undefined && task.status === "RUNNING" && (
                <span className="text-sm text-zinc-400">{(task.progress * 100).toFixed(0)}%</span>
              )}
            </div>

            {task.status === "RUNNING" && task.progress !== undefined && (
              <div className="w-full bg-zinc-800 rounded-full h-2">
                <div className="bg-indigo-500 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${(task.progress * 100).toFixed(0)}%` }} />
              </div>
            )}

            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              {task.createdAt && (
                <>
                  <dt className="text-zinc-400">Created</dt>
                  <dd>{new Date(task.createdAt).toLocaleString()}</dd>
                </>
              )}
              {task.startedAt && (
                <>
                  <dt className="text-zinc-400">Started</dt>
                  <dd>{new Date(task.startedAt).toLocaleString()}</dd>
                </>
              )}
              {task.endedAt && (
                <>
                  <dt className="text-zinc-400">Completed</dt>
                  <dd>{new Date(task.endedAt).toLocaleString()}</dd>
                </>
              )}
            </dl>

            {task.error && (
              <div className="bg-red-950/40 border border-red-900 rounded-lg p-3 text-sm text-red-300">
                {task.error}
              </div>
            )}
          </div>

          {task.status === "SUCCEEDED" && task.output && (
            <OutputViewer urls={task.output} />
          )}
        </>
      )}
    </div>
  );
}
