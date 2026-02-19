"use client";
import useSWR from "swr";
import { api, Task, OrgInfo } from "@/lib/api";
import { Zap, Film, ImageIcon, Mic, CreditCard } from "lucide-react";
import Link from "next/link";

const fetcher = (url: string) => api.get(url);

function StatusBadge({ status }: { status: Task["status"] }) {
  const cls = `badge badge-${status.toLowerCase()}`;
  const dot = status === "RUNNING" ? "animate-pulse " : "";
  return <span className={cls}><span className={`${dot}w-1.5 h-1.5 rounded-full bg-current`} />{status}</span>;
}

function StatCard({ icon: Icon, label, value, sub }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string;
}) {
  return (
    <div className="card flex items-center gap-4">
      <div className="w-10 h-10 rounded-lg bg-indigo-600/20 flex items-center justify-center">
        <Icon size={20} className="text-indigo-400" />
      </div>
      <div>
        <p className="text-xs text-zinc-400">{label}</p>
        <p className="text-xl font-semibold">{value}</p>
        {sub && <p className="text-xs text-zinc-500">{sub}</p>}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: org } = useSWR<OrgInfo>("/v1/organization", fetcher, { refreshInterval: 10000 });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-zinc-400 text-sm mt-1">Self-hosted AI media generation platform</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={CreditCard} label="Credit Balance"
          value={org?.creditBalance ?? "—"}
          sub={`Max ${org?.tier?.maxMonthlyCreditSpend ?? "—"}/month`} />
        <StatCard icon={Film} label="Video Models" value="7" sub="HunyuanVideo, LTX, CogVideoX…" />
        <StatCard icon={ImageIcon} label="Image Models" value="3" sub="FLUX.1, SD 3.5" />
        <StatCard icon={Mic} label="Audio Models" value="7" sub="Kokoro, Demucs, AudioCraft…" />
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Quick Start</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[
            { label: "Generate Image", href: "/generate?tab=text_to_image", icon: ImageIcon, desc: "FLUX.1 schnell / dev / SD3.5" },
            { label: "Image → Video", href: "/generate?tab=image_to_video", icon: Film, desc: "LTX-Video / HunyuanVideo" },
            { label: "Text → Speech", href: "/generate?tab=text_to_speech", icon: Mic, desc: "Kokoro / F5-TTS voice cloning" },
          ].map(({ label, href, icon: Icon, desc }) => (
            <Link key={href} href={href}
              className="flex items-center gap-3 p-3 rounded-lg border border-zinc-800 hover:border-indigo-500 hover:bg-indigo-600/5 transition-colors">
              <Icon size={18} className="text-indigo-400 shrink-0" />
              <div>
                <p className="text-sm font-medium">{label}</p>
                <p className="text-xs text-zinc-500">{desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">System Info</h2>
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between py-1.5 border-b border-zinc-800">
            <span className="text-zinc-400">API Version</span>
            <span className="font-mono text-xs">2024-11-06</span>
          </div>
          <div className="flex justify-between py-1.5 border-b border-zinc-800">
            <span className="text-zinc-400">Compatible with</span>
            <span>Runway Gen-4 SDK</span>
          </div>
          <div className="flex justify-between py-1.5 border-b border-zinc-800">
            <span className="text-zinc-400">Total endpoints</span>
            <span>15</span>
          </div>
          <div className="flex justify-between py-1.5">
            <span className="text-zinc-400">License</span>
            <span>Apache 2.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}
