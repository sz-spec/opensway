const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getKey(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("opensway_api_key") || "";
}

async function apiFetch(path: string, opts: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      "X-Runway-Version": "2024-11-06",
      Authorization: `Bearer ${getKey()}`,
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.error || "API error");
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  get: (path: string) => apiFetch(path),
  post: (path: string, body: unknown) =>
    apiFetch(path, { method: "POST", body: JSON.stringify(body) }),
  delete: (path: string) => apiFetch(path, { method: "DELETE" }),
};

export interface Task {
  id: string;
  status: "PENDING" | "THROTTLED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  createdAt?: string;
  startedAt?: string;
  endedAt?: string;
  progress?: number;
  output?: string[];
  error?: string;
}

export interface OrgInfo {
  creditBalance: number;
  tier: { maxMonthlyCreditSpend: number };
}

export const MODELS = {
  image_to_video: ["ltx_video", "hunyuan_video", "cogvideox"],
  text_to_video: ["ltx_video", "hunyuan_video"],
  video_to_video: ["animatediff"],
  text_to_image: ["flux_schnell", "flux_dev", "sd35_large"],
  character_performance: ["live_portrait", "musetalk", "sadtalker"],
  text_to_speech: ["kokoro", "f5_tts"],
  speech_to_speech: ["rvc"],
  sound_effect: ["audiocraft_audiogen"],
  voice_isolation: ["demucs"],
  voice_dubbing: ["dubbing_pipeline"],
} as const;

export const ENDPOINT_LABELS: Record<string, string> = {
  image_to_video: "Image → Video",
  text_to_video: "Text → Video",
  video_to_video: "Video → Video",
  text_to_image: "Text → Image",
  character_performance: "Character Animation",
  text_to_speech: "Text → Speech",
  speech_to_speech: "Speech → Speech",
  sound_effect: "Sound Effect",
  voice_isolation: "Voice Isolation",
  voice_dubbing: "Voice Dubbing",
};
