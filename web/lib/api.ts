// Thin typed client for the FastAPI worker.

export const WORKER_URL =
  process.env.NEXT_PUBLIC_WORKER_URL ?? "http://localhost:8000";

export type CaptionStyle = {
  fontFamily: string;
  fontSize: number;
  color: string;
  strokeColor: string;
  strokeWidth: number;
  highlightColor: string;
  maxWidth: number;
  position: { x: number; y: number };
};

export const DEFAULT_STYLE: CaptionStyle = {
  fontFamily: "Inter, Arial, sans-serif",
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
  const res = await fetch(`${WORKER_URL}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
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
  return `${WORKER_URL}/files/${jobId}/${relPath}`;
}

export async function getArtifact<T>(jobId: string, name: string): Promise<T> {
  const res = await fetch(`${fileUrl(jobId, name)}?t=${Date.now()}`);
  if (!res.ok) throw new Error(`could not load ${name} (${res.status})`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch(`${WORKER_URL}/health`).then((r) => r.json()),
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
  carousels: (jobId: string) =>
    post<{ carousels: string }>("/carousels", { job_id: jobId }),
  renderCarousels: (jobId: string) =>
    post<{ slides: string[] }>("/carousels/render", { job_id: jobId }),
  exportZip: (jobId: string) =>
    post<{ export: string }>("/export", { job_id: jobId }),
};
