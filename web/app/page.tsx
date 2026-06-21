"use client";

import { useEffect, useState } from "react";

const WORKER_URL =
  process.env.NEXT_PUBLIC_WORKER_URL ?? "http://localhost:8000";

type WorkerStatus = "checking" | "online" | "offline";

export default function Home() {
  const [worker, setWorker] = useState<WorkerStatus>("checking");

  useEffect(() => {
    let cancelled = false;
    fetch(`${WORKER_URL}/health`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled) setWorker(d?.ok ? "online" : "offline");
      })
      .catch(() => {
        if (!cancelled) setWorker("offline");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="wrap">
      <h1>Clip Engine</h1>
      <p className="tag">
        Turn one long video into N vertical, captioned, ready-to-post clips.
      </p>

      <div className="status">
        <span className={`dot ${worker}`} />
        <span>
          Worker:&nbsp;
          {worker === "checking"
            ? "checking…"
            : worker === "online"
            ? "online"
            : `offline (start the FastAPI worker on ${WORKER_URL})`}
        </span>
      </div>

      <p className="phase">Phase 0 — Scaffold. The pipeline lands in later phases.</p>
    </main>
  );
}
