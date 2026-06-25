"use client";

import { useEffect, useState } from "react";
import { CarouselEditor } from "./CarouselEditor";
import { ClipCard } from "./ClipCard";
import {
  api,
  CarouselManifest,
  Clip,
  fileUrl,
  getArtifact,
  getWorkerToken,
  getWorkerUrl,
  setWorkerToken,
  setWorkerUrl,
} from "../lib/api";
import {
  Draft,
  getDrafts,
  removeDraft,
  saveDraft,
  updateDraft,
} from "../lib/drafts";

type WorkerStatus = "checking" | "online" | "offline";

const STAGES = ["Download", "Transcribe", "Select", "Render", "Copy"];

function fmtBytes(n: number): string {
  return n >= 1e9 ? `${(n / 1e9).toFixed(2)}GB` : `${Math.round(n / 1e6)}MB`;
}

export default function Home() {
  const [worker, setWorker] = useState<WorkerStatus>("checking");
  const [url, setUrl] = useState("");
  const [count, setCount] = useState(3);
  const [splitScreen, setSplitScreen] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [carousels, setCarousels] = useState<CarouselManifest[]>([]);
  const [stage, setStage] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [exportHref, setExportHref] = useState<string | null>(null);
  const [workerInput, setWorkerInput] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [creator, setCreator] = useState("");
  const [step, setStep] = useState(-1);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  // the source we can re-run from (last uploaded/processed job)
  const [lastJobId, setLastJobId] = useState<string | null>(null);

  function checkHealth() {
    setWorker("checking");
    api
      .health()
      .then((d) => setWorker(d?.ok ? "online" : "offline"))
      .catch(() => setWorker("offline"));
  }

  useEffect(() => {
    setWorkerInput(getWorkerUrl());
    setTokenInput(getWorkerToken());
    setDrafts(getDrafts());
    checkHealth();
  }, []);

  function saveWorker() {
    setWorkerUrl(workerInput.trim());
    setWorkerToken(tokenInput.trim());
    checkHealth();
  }

  const running = stage !== null;

  async function pollRun(runId: string, name: string) {
    // Poll the worker for status until done/error. The pipeline runs in the
    // background on the worker, so the browser never holds a long request open.
    while (true) {
      let s;
      try {
        s = await api.jobStatus(runId);
      } catch {
        await new Promise((r) => setTimeout(r, 2000));
        continue;
      }
      setStep(s.step);
      setStage(s.stage ? `${s.stage}…` : null);
      if (s.job_id) {
        setJobId(s.job_id);
        setLastJobId(s.job_id);
        // remember this source as a draft the moment we know its job_id
        setDrafts(saveDraft({ jobId: s.job_id, name, createdAt: Date.now(), status: "uploaded" }));
      }
      if (s.state === "done") {
        const loaded = await getArtifact<Clip[]>(s.job_id!, "clips.json");
        setClips(loaded);
        setStep(s.stages.length);
        setStage(null);
        if (s.job_id) setDrafts(updateDraft(s.job_id, { status: "done" }));
        return;
      }
      if (s.state === "error") {
        setErr(s.error || "Pipeline failed");
        setStage(null);
        if (s.job_id) setDrafts(updateDraft(s.job_id, { status: "error" }));
        return;
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
  }

  async function startRun(body: { url?: string; job_id?: string }, name: string) {
    setErr(null);
    setClips([]);
    setCarousels([]);
    setExportHref(null);
    setStep(0);
    setStage("Starting…");
    if (body.job_id) setLastJobId(body.job_id);
    try {
      const { run_id } = await api.run({
        ...body,
        count,
        mode: splitScreen ? "split" : "single",
      });
      await pollRun(run_id, name);
    } catch (e) {
      setErr(String(e));
      setStage(null);
    }
  }

  function analyse() {
    return startRun({ url }, url);
  }

  function retry() {
    if (lastJobId) startRun({ job_id: lastJobId }, lastJobId);
  }

  async function uploadFile(file: File) {
    setErr(null);
    setClips([]);
    setCarousels([]);
    setStep(0);
    setStage("Uploading 0%…");
    try {
      const { job_id } = await api.uploadProgress(file, (pct, loaded, total) => {
        setStage(`Uploading ${Math.round(pct * 100)}% (${fmtBytes(loaded)} / ${fmtBytes(total)})`);
      });
      setLastJobId(job_id);
      setDrafts(saveDraft({ jobId: job_id, name: file.name, createdAt: Date.now(), status: "uploaded" }));
      await startRun({ job_id }, file.name);
    } catch (e) {
      setErr(`Upload failed: ${e}`);
      setStage(null);
    }
  }

  function resumeDraft(d: Draft) {
    setUrl("");
    startRun({ job_id: d.jobId }, d.name);
  }

  function deleteDraft(jobId: string) {
    setDrafts(removeDraft(jobId));
  }

  async function makeCarousels() {
    if (!jobId) return;
    setErr(null);
    try {
      setStage("Generating carousels…");
      await api.carousels(jobId, creator);
      setStage("Building split-screen slides…");
      const { carousels: manifest } = await api.renderCarousels(jobId);
      setCarousels(manifest);
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

      <section className="howto">
        <ol>
          <li>Paste a video link (YouTube works best).</li>
          <li>Choose how many clips you want.</li>
          <li>
            Hit <strong>Create clips</strong> — captions are added automatically.
          </li>
        </ol>
      </section>

      <section className="panel">
        <input
          className="url"
          placeholder="Paste a video link…"
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
        <div className="createrow">
          <button className="primary" onClick={analyse} disabled={running || !url}>
            Create clips
          </button>
          <span className="or2">or</span>
          <label className={`uploadbtn${running ? " disabled" : ""}`}>
            Upload a video file
            <input
              type="file"
              accept="video/*,audio/*"
              hidden
              disabled={running}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadFile(f);
              }}
            />
          </label>
        </div>
        <p className="hint">
          YouTube/Drive links are often blocked when downloaded from a server —
          uploading the file always works.
        </p>
      </section>

      {step >= 0 ? (
        <ol className="stepper">
          {STAGES.map((s, i) => (
            <li
              key={s}
              className={
                i < step ? "done" : i === step && running ? "active" : i === step ? "done" : ""
              }
            >
              <span className="num">{i < step || (i === step && !running) ? "✓" : i + 1}</span>
              {s}
            </li>
          ))}
        </ol>
      ) : null}
      {stage ? <p className="stage">⏳ {stage}</p> : null}
      {err ? (
        <div className="errbox">
          <p className="stage err">⚠ {err}</p>
          {lastJobId && !running ? (
            <button className="ghost" onClick={retry}>
              ↻ Retry (your file is saved — no re-upload)
            </button>
          ) : null}
        </div>
      ) : null}

      {clips.length > 0 ? (
        <>
          <div className="toolbar">
            <label className="creator">
              Creator
              <select
                value={creator}
                onChange={(e) => setCreator(e.target.value)}
                disabled={running}
              >
                <option value="">Auto</option>
                <option value="A">Speaker A</option>
                <option value="B">Speaker B</option>
              </select>
            </label>
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
                mode={splitScreen ? "split" : "single"}
                onClipChange={onClipChange}
              />
            ))}
          </div>
        </>
      ) : null}

      {carousels.length > 0 && jobId ? (
        <CarouselEditor jobId={jobId} carousels={carousels} />
      ) : null}

      {drafts.length > 0 ? (
        <section className="drafts">
          <h2>Drafts</h2>
          <p className="hint">
            Previously uploaded/processed sources. Re-run any of them without
            re-uploading.
          </p>
          <ul className="draftlist">
            {drafts.map((d) => (
              <li key={d.jobId} className="draftrow">
                <span className={`ddot ${d.status ?? ""}`} />
                <span className="dname" title={d.name}>
                  {d.name || d.jobId}
                </span>
                <span className="dmeta">
                  {new Date(d.createdAt).toLocaleString()}
                </span>
                <button
                  className="ghost"
                  onClick={() => resumeDraft(d)}
                  disabled={running}
                >
                  Create clips
                </button>
                <button
                  className="ghost del"
                  onClick={() => deleteDraft(d.jobId)}
                  disabled={running}
                  title="Remove from list"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {worker === "offline" ? (
        <p className="footnote">
          Engine is waking up (it sleeps when idle) or starting up — give it a few
          seconds and try again. Advanced connection settings are below.
        </p>
      ) : null}

      <details className="advanced">
        <summary>Advanced — worker connection</summary>
        <div className="advbody">
          <label className="lbl">Worker URL</label>
          <input
            className="url"
            placeholder="https://clip-engine-worker.onrender.com"
            value={workerInput}
            onChange={(e) => setWorkerInput(e.target.value)}
          />
          <label className="lbl">Worker token (only if you set one)</label>
          <div className="connrow">
            <input
              className="url"
              type="password"
              placeholder="optional access token"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
            />
            <button className="ghost" onClick={saveWorker}>
              Save &amp; test
            </button>
          </div>
        </div>
      </details>
    </main>
  );
}
