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

export type RunStatus = {
  id: string;
  step: number;
  state: "pending" | "running" | "done" | "error";
  stage: string | null;
  error: string | null;
  job_id: string | null;
  stages: string[];
  elapsed: number;
};

export const api = {
  health: () => fetch(`${getWorkerUrl()}/health`).then((r) => r.json()),
  ingest: (url: string) => post<{ job_id: string }>("/ingest", { url }),
  run: (body: {
    url?: string;
    job_id?: string;
    count: number;
    mode: "single" | "split";
  }) => post<{ run_id: string }>("/run", body),
  jobStatus: async (runId: string): Promise<RunStatus> => {
    const res = await fetch(`${getWorkerUrl()}/jobs/${runId}?t=${Date.now()}`);
    if (!res.ok) throw new Error(`status ${res.status}`);
    return res.json();
  },
  upload: async (file: File): Promise<{ job_id: string }> => {
    const token = getWorkerToken();
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${getWorkerUrl()}/upload`, {
      method: "POST",
      headers: { ...(token ? { "x-worker-token": token } : {}) },
      body: fd,
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
    return res.json();
  },
  // Upload with progress — uses XHR because fetch() can't report upload bytes.
  uploadProgress: (
    file: File,
    onProgress: (pct: number, loaded: number, total: number) => void
  ): Promise<{ job_id: string }> =>
    new Promise((resolve, reject) => {
      const token = getWorkerToken();
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${getWorkerUrl()}/upload`);
      if (token) xhr.setRequestHeader("x-worker-token", token);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(e.loaded / e.total, e.loaded, e.total);
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            reject(new Error("bad response from worker"));
          }
        } else {
          let detail = `${xhr.status}`;
          try {
            const j = JSON.parse(xhr.responseText);
            if (j?.detail) detail = j.detail;
          } catch {
            /* ignore */
          }
          reject(new Error(detail));
        }
      };
      xhr.onerror = () => reject(new Error("network error during upload"));
      const fd = new FormData();
      fd.append("file", file);
      xhr.send(fd);
    }),
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
    post<{ carousels: CarouselManifest[] }>("/carousels/render", { job_id: jobId }),
  renderSlide: (jobId: string, s: SlideEdit) =>
    post<{ slide: SlideEntry }>("/carousels/slide", { job_id: jobId, ...s }),
  exportZip: (jobId: string) =>
    post<{ export: string }>("/export", { job_id: jobId }),
};

export type SlideEntry = {
  index: number;
  top_text: string;
  bottom_text: string;
  t_top: number;
  t_bottom: number;
  file: string;
};

export type CarouselManifest = {
  number: number;
  title: string;
  slides: SlideEntry[];
};

export type SlideEdit = {
  number: number;
  index: number;
  top_text: string;
  bottom_text: string;
  t_top: number;
  t_bottom: number;
};
