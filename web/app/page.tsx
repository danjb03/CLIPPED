"use client";

import { useCallback, useEffect, useState } from "react";
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
  ServerDraft,
  setWorkerToken,
  setWorkerUrl,
} from "../lib/api";

type WorkerStatus = "checking" | "online" | "offline";

const DEFAULT_STAGES = ["Download", "Transcribe", "Storylines", "Slides"];

function fmtBytes(n: number): string {
  return n >= 1e9 ? `${(n / 1e9).toFixed(2)}GB` : `${Math.round(n / 1e6)}MB`;
}

async function downloadBlob(url: string, name: string) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`download ${res.status}`);
  const blob = await res.blob();
  const obj = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = obj;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(obj), 1000);
}

export default function Home() {
  const [worker, setWorker] = useState<WorkerStatus>("checking");
  const [url, setUrl] = useState("");
  const [makeClips, setMakeClips] = useState(false);
  const [count, setCount] = useState(3);
  const [splitScreen, setSplitScreen] = useState(false);
  const [creator, setCreator] = useState("");

  const [jobId, setJobId] = useState<string | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [carousels, setCarousels] = useState<CarouselManifest[]>([]);
  const [stage, setStage] = useState<string | null>(null);
  const [stages, setStages] = useState<string[]>(DEFAULT_STAGES);
  const [err, setErr] = useState<string | null>(null);
  const [workerInput, setWorkerInput] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [step, setStep] = useState(-1);
  const [drafts, setDrafts] = useState<ServerDraft[]>([]);
  const [lastJobId, setLastJobId] = useState<string | null>(null);
  const [zipBusy, setZipBusy] = useState(false);

  function checkHealth() {
    setWorker("checking");
    api
      .health()
      .then((d) => setWorker(d?.ok ? "online" : "offline"))
      .catch(() => setWorker("offline"));
  }

  const refreshDrafts = useCallback(() => {
    api
      .drafts()
      .then((d) => setDrafts(d.drafts))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setWorkerInput(getWorkerUrl());
    setTokenInput(getWorkerToken());
    checkHealth();
    refreshDrafts();
  }, [refreshDrafts]);

  function saveWorker() {
    setWorkerUrl(workerInput.trim());
    setWorkerToken(tokenInput.trim());
    checkHealth();
    refreshDrafts();
  }

  const running = stage !== null;

  async function loadResults(job: string, withClips: boolean) {
    try {
      const manifest = await getArtifact<CarouselManifest[]>(
        job,
        "carousels/manifest.json"
      );
      setCarousels(manifest);
    } catch {
      /* no carousels yet */
    }
    if (withClips) {
      try {
        setClips(await getArtifact<Clip[]>(job, "clips.json"));
      } catch {
        /* no clips */
      }
    }
  }

  async function pollRun(runId: string, withClips: boolean) {
    // The pipeline runs in the background on the worker; we poll status so no
    // request ever stays open long enough for a proxy to kill it.
    while (true) {
      let s;
      try {
        s = await api.jobStatus(runId);
      } catch {
        await new Promise((r) => setTimeout(r, 2000));
        continue;
      }
      if (s.stages?.length) setStages(s.stages);
      setStep(s.step);
      setStage(s.stage ? `${s.stage}…` : null);
      if (s.job_id) {
        setJobId(s.job_id);
        setLastJobId(s.job_id);
      }
      if (s.state === "done") {
        await loadResults(s.job_id!, withClips);
        setStep(s.stages.length);
        setStage(null);
        refreshDrafts();
        return;
      }
      if (s.state === "error") {
        setErr(s.error || "Pipeline failed");
        setStage(null);
        refreshDrafts();
        return;
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
  }

  async function startRun(body: { url?: string; job_id?: string }) {
    setErr(null);
    setClips([]);
    setCarousels([]);
    setStages(
      makeClips ? [...DEFAULT_STAGES, "Select", "Render", "Copy"] : DEFAULT_STAGES
    );
    setStep(0);
    setStage("Starting…");
    if (body.job_id) setLastJobId(body.job_id);
    try {
      const { run_id } = await api.run({
        ...body,
        count,
        mode: splitScreen ? "split" : "single",
        make_clips: makeClips,
        creator: creator || null,
      });
      await pollRun(run_id, makeClips);
    } catch (e) {
      setErr(String(e));
      setStage(null);
    }
  }

  function retry() {
    if (lastJobId) startRun({ job_id: lastJobId });
  }

  async function uploadFile(file: File) {
    setErr(null);
    setClips([]);
    setCarousels([]);
    setStep(0);
    setStage("Uploading 0%…");
    try {
      const { job_id } = await api.uploadProgress(file, (pct, loaded, total) => {
        setStage(
          `Uploading ${Math.round(pct * 100)}% (${fmtBytes(loaded)} / ${fmtBytes(total)})`
        );
      });
      refreshDrafts();
      await startRun({ job_id });
    } catch (e) {
      setErr(`Upload failed: ${e}`);
      setStage(null);
    }
  }

  // Re-run just the carousel stages on an existing transcribed job.
  async function regenerateCarousels(job: string) {
    setErr(null);
    setCarousels([]);
    setJobId(job);
    setLastJobId(job);
    setStages(["Storylines", "Slides"]);
    setStep(0);
    setStage("Starting…");
    try {
      const { run_id } = await api.carouselsRun(job, creator);
      await pollRun(run_id, false);
    } catch (e) {
      setErr(String(e));
      setStage(null);
    }
  }

  function resumeDraft(d: ServerDraft) {
    setUrl("");
    if (d.has_transcript) {
      // Transcript already exists — skip straight to carousels (fast + cheap).
      regenerateCarousels(d.job_id);
    } else {
      startRun({ job_id: d.job_id });
    }
  }

  async function openDraft(d: ServerDraft) {
    setErr(null);
    setJobId(d.job_id);
    setLastJobId(d.job_id);
    setClips([]);
    setCarousels([]);
    await loadResults(d.job_id, d.has_clips);
  }

  async function deleteDraftRow(job: string) {
    try {
      await api.deleteDraft(job);
    } catch (e) {
      setErr(String(e));
    }
    refreshDrafts();
  }

  async function downloadCarouselZip() {
    if (!jobId) return;
    setZipBusy(true);
    setErr(null);
    try {
      await api.exportCarousels(jobId);
      await downloadBlob(
        `${fileUrl(jobId, "carousels.zip")}?t=${Date.now()}`,
        "carousels.zip"
      );
    } catch (e) {
      setErr(String(e));
    } finally {
      setZipBusy(false);
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
          <li>Upload your podcast (or paste a link).</li>
          <li>
            Hit <strong>Create carousels</strong> — it transcribes, finds the most
            viral storylines, and builds split-screen slides automatically.
          </li>
          <li>Edit any slide’s text or frame, then download the PNGs.</li>
        </ol>
      </section>

      <section className="panel">
        <input
          className="url"
          placeholder="Paste a video link (optional — uploading is more reliable)…"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={running}
        />
        <div className="createrow">
          <label className={`uploadbtn primarylike${running ? " disabled" : ""}`}>
            ⬆ Upload podcast &amp; create carousels
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
          <span className="or2">or</span>
          <button
            className="primary"
            onClick={() => startRun({ url })}
            disabled={running || !url}
          >
            Create from link
          </button>
        </div>

        <div className="opts">
          <label className="creator">
            Creator voice
            <select
              value={creator}
              onChange={(e) => setCreator(e.target.value)}
              disabled={running}
            >
              <option value="">Auto (most words)</option>
              <option value="A">Speaker A</option>
              <option value="B">Speaker B</option>
            </select>
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={makeClips}
              onChange={(e) => setMakeClips(e.target.checked)}
              disabled={running}
            />
            Also make video clips
          </label>
          {makeClips ? (
            <>
              <label>
                Clips (N)
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={count}
                  onChange={(e) => setCount(Number(e.target.value))}
                  disabled={running}
                />
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={splitScreen}
                  onChange={(e) => setSplitScreen(e.target.checked)}
                  disabled={running}
                />
                Split-screen clips
              </label>
            </>
          ) : null}
        </div>
      </section>

      {step >= 0 ? (
        <ol className="stepper">
          {stages.map((s, i) => (
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

      {carousels.length > 0 && jobId ? (
        <>
          <div className="toolbar">
            <button onClick={downloadCarouselZip} disabled={running || zipBusy}>
              {zipBusy ? "Zipping…" : "⬇ Download all carousels (.zip)"}
            </button>
            <button
              className="ghost"
              onClick={() => regenerateCarousels(jobId)}
              disabled={running}
            >
              ↻ Regenerate storylines
            </button>
          </div>
          <CarouselEditor jobId={jobId} carousels={carousels} />
        </>
      ) : null}

      {clips.length > 0 && jobId ? (
        <>
          <h2>Video clips</h2>
          <div className="grid">
            {clips.map((clip, i) => (
              <ClipCard
                key={i}
                jobId={jobId}
                index={i}
                clip={clip}
                mode={splitScreen ? "split" : "single"}
                onClipChange={onClipChange}
              />
            ))}
          </div>
        </>
      ) : null}

      {drafts.length > 0 ? (
        <section className="drafts">
          <h2>Library</h2>
          <p className="hint">
            Every podcast you’ve uploaded, saved on the server — open results,
            re-run, or delete from any device.
          </p>
          <ul className="draftlist">
            {drafts.map((d) => (
              <li key={d.job_id} className="draftrow">
                <span
                  className={`ddot ${d.has_carousels ? "done" : d.has_transcript ? "uploaded" : ""}`}
                />
                <span className="dname" title={d.name}>
                  {d.name || d.job_id}
                </span>
                <span className="dmeta">
                  {new Date(d.created * 1000).toLocaleString()}
                </span>
                {d.has_carousels ? (
                  <button className="ghost" onClick={() => openDraft(d)} disabled={running}>
                    Open
                  </button>
                ) : null}
                <button className="ghost" onClick={() => resumeDraft(d)} disabled={running}>
                  {d.has_transcript ? "New carousels" : "Process"}
                </button>
                <button
                  className="ghost del"
                  onClick={() => deleteDraftRow(d.job_id)}
                  disabled={running}
                  title="Delete from server (frees disk space)"
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
