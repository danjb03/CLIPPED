// Thin typed client for the FastAPI worker.
//
// The worker URL is resolved at runtime (not baked in at build time) so the
// deployed UI can point at any local tunnel (cloudflared/ngrok) you paste in.
// Priority: localStorage("workerUrl") > NEXT_PUBLIC_WORKER_URL > localhost.

// The hosted worker. onrender.com URLs are stable, so this is the baked-in
// default — visitors don't need to enter anything. NEXT_PUBLIC_WORKER_URL or the
// Advanced panel can still override it.
const ENV_WORKER_URL =
  process.env.NEXT_PUBLIC_WORKER_URL ?? "https://clip-engine-worker.onrender.com";

export function getWorkerUrl(): string {
  if (typeof window !== "undefined") {
    const saved = window.localStorage.getItem("workerUrl");
    if (saved) return saved.replace(/\/$/, "");
  }
  return ENV_WORKER_URL.replace(/\/$/, "");
}

export function setWorkerUrl(url: string): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem("workerUrl", url.replace(/\/$/, ""));
  }
}

export function getWorkerToken(): string {
  if (typeof window !== "undefined") {
    const saved = window.localStorage.getItem("workerToken");
    if (saved) return saved;
  }
  return process.env.NEXT_PUBLIC_WORKER_TOKEN ?? "";
}

export function setWorkerToken(token: string): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem("workerToken", token);
  }
}

export type CaptionStyle = {
  fontFamily: string;
  assFont: string; // font installed on the worker, used by the ffmpeg burn
  fontSize: number;
  color: string;
  strokeColor: string;
  strokeWidth: number;
  highlightColor: string;
  maxWidth: number;
  position: { x: number; y: number };
};

// Fonts bundled in the worker container (see Dockerfile).
export const FONTS = [
  "Liberation Sans",
  "Montserrat",
  "Open Sans",
  "Noto Sans",
  "DejaVu Sans",
];

export const DEFAULT_STYLE: CaptionStyle = {
  fontFamily: "Inter, Arial, sans-serif",
  assFont: "Liberation Sans",
  fontSize: 84,
  color: "#ffffff",
  strokeColor: "#000000",
  strokeWidth: 10,
  highlightColor: "#ffe600",
  maxWidth: 0.9,
  position: { x: 0.5, y: 0.78 },
};

export type Clip = {
  start: number;
  end: number;
  hook: string;
  reason: string;
  speaker_focus: "A" | "B" | "both";
  copy?: string;
};

export type Carousel = {
  number: number;
  title: string;
  slides: string[];
};

async function post<T>(path: string, body: unknown): Promise<T> {
  const token = getWorkerToken();
  const res = await fetch(`${getWorkerUrl()}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { "x-worker-token": token } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (j?.detail) detail = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export function fileUrl(jobId: string, relPath: string): string {
  return `${getWorkerUrl()}/files/${jobId}/${relPath}`;
}

export async function getArtifact<T>(jobId: string, name: string): Promise<T> {
  const res = await fetch(`${fileUrl(jobId, name)}?t=${Date.now()}`);
  if (!res.ok) throw new Error(`could not load ${name} (${res.status})`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch(`${getWorkerUrl()}/health`).then((r) => r.json()),
  ingest: (url: string) => post<{ job_id: string }>("/ingest", { url }),
  transcribe: (jobId: string) =>
    post<{ transcript: string }>("/transcribe", { job_id: jobId }),
  select: (jobId: string, count: number) =>
    post<{ clips: string }>("/select", { job_id: jobId, count }),
  render: (jobId: string, mode: "single" | "split" = "single") =>
    post<{ renders: string[] }>("/render", { job_id: jobId, mode }),
  renderOne: (
    jobId: string,
    index: number,
    style: CaptionStyle,
    mode: "single" | "split" = "single"
  ) => post<{ render: string }>("/render/one", { job_id: jobId, index, style, mode }),
  regenerate: (jobId: string, index: number) =>
    post<{ clip: Clip }>("/select/regenerate", { job_id: jobId, index }),
  copy: (jobId: string) => post<{ clips: string }>("/copy", { job_id: jobId }),
  carousels: (jobId: string, creator?: string) =>
    post<{ carousels: string }>("/carousels", {
      job_id: jobId,
      creator: creator || null,
    }),
  renderCarousels: (jobId: string) =>
    post<{ slides: string[] }>("/carousels/render", { job_id: jobId }),
  exportZip: (jobId: string) =>
    post<{ export: string }>("/export", { job_id: jobId }),
};
