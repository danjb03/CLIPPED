"use client";

import { useEffect, useState } from "react";
import { ClipCard } from "./ClipCard";
import {
  api,
  Carousel,
  Clip,
  fileUrl,
  getArtifact,
  WORKER_URL,
} from "../lib/api";

type WorkerStatus = "checking" | "online" | "offline";

export default function Home() {
  const [worker, setWorker] = useState<WorkerStatus>("checking");
  const [url, setUrl] = useState("");
  const [count, setCount] = useState(3);
  const [splitScreen, setSplitScreen] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [carousels, setCarousels] = useState<Carousel[]>([]);
  const [stage, setStage] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [exportHref, setExportHref] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then((d) => setWorker(d?.ok ? "online" : "offline"))
      .catch(() => setWorker("offline"));
  }, []);

  const running = stage !== null;

  async function analyse() {
    setErr(null);
    setClips([]);
    setCarousels([]);
    setExportHref(null);
    try {
      setStage("Downloading video…");
      const { job_id } = await api.ingest(url);
      setJobId(job_id);

      setStage("Transcribing + diarising (this can take a while)…");
      await api.transcribe(job_id);

      setStage("Selecting the best moments…");
      await api.select(job_id, count);

      setStage("Rendering captioned clips…");
      await api.render(job_id);

      setStage("Writing post copy…");
      await api.copy(job_id);

      const loaded = await getArtifact<Clip[]>(job_id, "clips.json");
      setClips(loaded);
      setStage(null);
    } catch (e) {
      setErr(String(e));
      setStage(null);
    }
  }

  async function makeCarousels() {
    if (!jobId) return;
    setErr(null);
    try {
      setStage("Generating carousels…");
      await api.carousels(jobId);
      setStage("Rendering carousel slides…");
      await api.renderCarousels(jobId);
      const loaded = await getArtifact<Carousel[]>(jobId, "carousels.json");
      setCarousels(loaded);
      setStage(null);
    } catch (e) {
      setErr(String(e));
      setStage(null);
    }
  }

  async function doExport() {
    if (!jobId) return;
    setErr(null);
    try {
      setStage("Bundling export…");
      await api.exportZip(jobId);
      setExportHref(fileUrl(jobId, "export.zip"));
      setStage(null);
    } catch (e) {
      setErr(String(e));
      setStage(null);
    }
  }

  function onClipChange(index: number, clip: Clip) {
    setClips((cs) => cs.map((c, i) => (i === index ? clip : c)));
  }

  return (
    <main className="wrap">
      <header className="head">
        <h1>Clip Engine</h1>
        <div className="status-pill">
          <span className={`dot ${worker}`} />
          {worker === "online" ? "worker online" : worker === "offline" ? "worker offline" : "…"}
        </div>
      </header>

      <section className="panel">
        <input
          className="url"
          placeholder="Paste a video URL…"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={running}
        />
        <div className="opts">
          <label>
            Posts (N)
            <input
              type="number"
              min={1}
              max={10}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              disabled={running}
            />
          </label>
          <label>
            Format
            <select disabled>
              <option>9:16 (vertical)</option>
            </select>
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={splitScreen}
              onChange={(e) => setSplitScreen(e.target.checked)}
              disabled={running}
            />
            Split-screen
            <span className="hint">(Phase 4 — falls back to single crop for now)</span>
          </label>
        </div>
        <button className="primary" onClick={analyse} disabled={running || !url}>
          Analyse &amp; generate
        </button>
      </section>

      {stage ? <p className="stage">⏳ {stage}</p> : null}
      {err ? <p className="stage err">⚠ {err}</p> : null}

      {clips.length > 0 ? (
        <>
          <div className="toolbar">
            <button onClick={makeCarousels} disabled={running}>
              Generate carousels
            </button>
            <button onClick={doExport} disabled={running}>
              Export .zip
            </button>
            {exportHref ? (
              <a className="dl" href={exportHref}>
                ⬇ Download export.zip
              </a>
            ) : null}
          </div>

          <div className="grid">
            {clips.map((clip, i) => (
              <ClipCard
                key={i}
                jobId={jobId!}
                index={i}
                clip={clip}
                onClipChange={onClipChange}
              />
            ))}
          </div>
        </>
      ) : null}

      {carousels.length > 0 && jobId ? (
        <section className="carousels">
          <h2>Carousels</h2>
          {carousels.map((c) => (
            <div key={c.number} className="carousel">
              <p className="ctitle">
                Carousel {c.number}: {c.title}
              </p>
              <div className="slides">
                {c.slides.map((_, i) => (
                  <img
                    key={i}
                    className="slide"
                    alt={`carousel ${c.number} slide ${i + 1}`}
                    src={fileUrl(jobId, `carousels/carousel_${c.number}/slide_${i + 1}.png`)}
                  />
                ))}
              </div>
            </div>
          ))}
        </section>
      ) : null}

      {worker === "offline" ? (
        <p className="footnote">
          Start the worker: <code>cd worker &amp;&amp; uvicorn main:app --port 8000</code>{" "}
          ({WORKER_URL})
        </p>
      ) : null}
    </main>
  );
}
