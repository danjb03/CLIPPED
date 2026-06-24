// Locally-remembered jobs ("drafts") so an uploaded/processed source can be
// re-run without re-uploading. Stored in the browser; the actual source files
// live on the worker (persisted via a Render disk).

export type Draft = {
  jobId: string;
  name: string;
  createdAt: number;
  status?: "uploaded" | "done" | "error";
};

const KEY = "drafts";

export function getDrafts(): Draft[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Draft[]) : [];
  } catch {
    return [];
  }
}

function write(drafts: Draft[]) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(KEY, JSON.stringify(drafts.slice(0, 30)));
  }
}

export function saveDraft(d: Draft): Draft[] {
  const existing = getDrafts().filter((x) => x.jobId !== d.jobId);
  const next = [d, ...existing];
  write(next);
  return next;
}

export function updateDraft(jobId: string, patch: Partial<Draft>): Draft[] {
  const next = getDrafts().map((d) => (d.jobId === jobId ? { ...d, ...patch } : d));
  write(next);
  return next;
}

export function removeDraft(jobId: string): Draft[] {
  const next = getDrafts().filter((d) => d.jobId !== jobId);
  write(next);
  return next;
}
