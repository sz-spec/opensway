"use client";
import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, MODELS, ENDPOINT_LABELS } from "@/lib/api";
import { Send, Loader2 } from "lucide-react";

const TABS = Object.keys(MODELS) as (keyof typeof MODELS)[];

const LANG_OPTIONS = [
  "en","es","fr","de","pt","zh","ja","ko","ar","ru","it","nl","tr","pl",
  "sv","hi","id","fil","ms","ro","uk","el","cs","da","fi","bg","hr","sk","ta"
];

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-zinc-300">{label}</label>
      {children}
    </div>
  );
}

const inputCls = "w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";
const selectCls = inputCls;

function GenerateForm({ tab }: { tab: keyof typeof MODELS }) {
  const router = useRouter();
  const [form, setForm] = useState<Record<string, string | number>>({
    model: MODELS[tab][0],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (key: string, val: string | number) => setForm((f) => ({ ...f, [key]: val }));

  async function submit() {
    setError("");
    setLoading(true);
    try {
      const endpoint = tab.replace(/_/g, "_");
      const task = await api.post(`/v1/${endpoint}`, form);
      // Store task ID in localStorage for Tasks page
      const existing = JSON.parse(localStorage.getItem("opensway_tasks") || "[]");
      localStorage.setItem("opensway_tasks", JSON.stringify([task.id, ...existing].slice(0, 100)));
      router.push(`/tasks/${task.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Model selector */}
      <Field label="Model">
        <select className={selectCls} value={form.model as string}
          onChange={(e) => set("model", e.target.value)}>
          {MODELS[tab].map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </Field>

      {/* Text prompt */}
      {["text_to_image","text_to_video","image_to_video","video_to_video","sound_effect","text_to_speech"].includes(tab) && (
        <Field label="Prompt">
          <textarea className={inputCls} rows={3}
            placeholder="Describe what to generate…"
            value={form.promptText as string || ""}
            onChange={(e) => set("promptText", e.target.value)} />
        </Field>
      )}

      {/* Image URI */}
      {["image_to_video","character_performance"].includes(tab) && (
        <Field label="Source Image URL">
          <input className={inputCls} type="url"
            placeholder="https://…"
            value={form.promptImage as string || ""}
            onChange={(e) => set("promptImage", e.target.value)} />
        </Field>
      )}

      {/* Video URI */}
      {["video_to_video","voice_isolation","voice_dubbing","speech_to_speech"].includes(tab) && (
        <Field label="Media URL">
          <input className={inputCls} type="url"
            placeholder="https://…"
            value={(form.videoUri || form.audioUri) as string || ""}
            onChange={(e) => {
              if (tab === "video_to_video") set("videoUri", e.target.value);
              else set("audioUri", e.target.value);
            }} />
        </Field>
      )}

      {/* Reference video for character performance */}
      {tab === "character_performance" && (
        <Field label="Reference (Driving) Video URL">
          <input className={inputCls} type="url"
            placeholder="https://…"
            value={form.reference as string || ""}
            onChange={(e) => set("reference", e.target.value)} />
        </Field>
      )}

      {/* Ratio */}
      {["image_to_video","text_to_video","video_to_video","text_to_image"].includes(tab) && (
        <Field label="Aspect Ratio">
          <select className={selectCls} value={form.ratio as string || "1280:720"}
            onChange={(e) => set("ratio", e.target.value)}>
            {["1280:720","720:1280","1024:1024","1104:832","832:1104","960:960"].map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </Field>
      )}

      {/* Duration */}
      {["image_to_video","text_to_video"].includes(tab) && (
        <Field label={`Duration: ${form.duration ?? 5}s`}>
          <input type="range" min={2} max={10} step={1}
            value={form.duration as number ?? 5}
            onChange={(e) => set("duration", parseInt(e.target.value))}
            className="w-full accent-indigo-500" />
        </Field>
      )}

      {/* Sound effect duration */}
      {tab === "sound_effect" && (
        <Field label={`Duration: ${form.duration ?? 5}s`}>
          <input type="range" min={1} max={30} step={0.5}
            value={form.duration as number ?? 5}
            onChange={(e) => set("duration", parseFloat(e.target.value))}
            className="w-full accent-indigo-500" />
        </Field>
      )}

      {/* Target language for dubbing */}
      {tab === "voice_dubbing" && (
        <Field label="Target Language">
          <select className={selectCls} value={form.targetLang as string || "en"}
            onChange={(e) => set("targetLang", e.target.value)}>
            {LANG_OPTIONS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
      )}

      {/* Seed */}
      <Field label="Seed (optional)">
        <input className={inputCls} type="number"
          placeholder="Random"
          value={form.seed as number || ""}
          onChange={(e) => e.target.value ? set("seed", parseInt(e.target.value)) : set("seed", "")} />
      </Field>

      {/* Webhook */}
      <Field label="Webhook URL (optional)">
        <input className={inputCls} type="url"
          placeholder="https://your-server.com/webhook"
          value={form.webhookUrl as string || ""}
          onChange={(e) => set("webhookUrl", e.target.value)} />
      </Field>

      {error && (
        <div className="bg-red-950/40 border border-red-900 rounded-lg px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      <button
        onClick={submit}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm transition-colors">
        {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        {loading ? "Submitting…" : "Generate"}
      </button>
    </div>
  );
}

function GenerateInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tabParam = searchParams.get("tab") as keyof typeof MODELS | null;
  const [tab, setTab] = useState<keyof typeof MODELS>(
    TABS.includes(tabParam as keyof typeof MODELS) ? (tabParam as keyof typeof MODELS) : "text_to_image"
  );

  useEffect(() => {
    if (tabParam && TABS.includes(tabParam as keyof typeof MODELS)) {
      setTab(tabParam as keyof typeof MODELS);
    }
  }, [tabParam]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Generate</h1>
        <p className="text-zinc-400 text-sm mt-1">Submit a new AI generation task</p>
      </div>

      <div className="flex gap-2 flex-wrap">
        {TABS.map((t) => (
          <button key={t}
            onClick={() => { setTab(t); router.replace(`/generate?tab=${t}`); }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
              ${tab === t ? "bg-indigo-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-zinc-100"}`}>
            {ENDPOINT_LABELS[t]}
          </button>
        ))}
      </div>

      <div className="card max-w-xl">
        <GenerateForm key={tab} tab={tab} />
      </div>
    </div>
  );
}

export default function GeneratePage() {
  return (
    <Suspense>
      <GenerateInner />
    </Suspense>
  );
}
